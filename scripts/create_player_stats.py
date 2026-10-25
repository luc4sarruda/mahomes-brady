"""Build game-level passing statistics for the first 131 starts of each QB.

Run from the project root:
    python3 scripts/create_player_stats.py

Inputs:
    data/processed/qb_first_131_starts.parquet
    data/raw/play_by_play/pbp_{season}.parquet

Outputs:
    data/processed/qb_pass_attempts.parquet
    data/processed/qb_game_stats.parquet
    data/processed/qb_game_stats.csv
    data/processed/qb_master_stats.parquet

Scope: official-style passing statistics only. QB EPA, sacks and scrambles
will be analyzed in a separate, explicitly defined dropback pipeline.
"""

from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "data/processed/qb_first_131_starts.parquet"
PBP_DIR = ROOT / "data/raw/play_by_play"
OUTPUT_DIR = ROOT / "data/processed"

# The fields are documented in the nflfastR play-by-play data dictionary.
PBP_COLUMNS = [
    "game_id", "play_id", "posteam", "passer_player_id", "play_type",
    "pass_attempt", "sack", "qb_scramble", "qb_spike", "complete_pass",
    "passing_yards", "pass_touchdown", "interception", "two_point_attempt",
]
COUNT_COLUMNS = [
    "attempts", "completions", "passing_yards", "passing_tds", "interceptions",
]


def load_master() -> pl.DataFrame:
    if not MASTER_PATH.is_file():
        raise FileNotFoundError(f"Master table not found: {MASTER_PATH}")

    master = pl.read_parquet(MASTER_PATH)
    required = {"player_id", "player_name", "game_id", "start_no", "season", "team"}
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"Missing master table columns: {sorted(missing)}")

    if master.height != 262:
        raise ValueError(f"Expected 262 master rows, found {master.height}")

    distinct_pairs = master.select(
        pl.struct("player_id", "game_id").n_unique()
    ).item()
    if distinct_pairs != 262:
        raise ValueError("Duplicate quarterback-game pairs in the master table")

    for player, subset in master.group_by("player_name"):
        if subset.height != 131 or sorted(subset["start_no"].to_list()) != list(range(1, 132)):
            raise ValueError(f"Incorrect start numbering for {player}")

    return master.with_columns(pl.col("player_id").cast(pl.String))


def load_relevant_plays(master: pl.DataFrame) -> pl.DataFrame:
    frames = []

    for season in sorted(master["season"].unique().to_list()):
        path = PBP_DIR / f"pbp_{season}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Missing season data: {path}")

        game_ids = master.filter(pl.col("season") == season)["game_id"].to_list()
        lazy = pl.scan_parquet(path)
        schema = lazy.collect_schema()
        missing = sorted(set(PBP_COLUMNS) - set(schema.names()))
        if missing:
            raise ValueError(f"PBP {season} missing columns: {missing}")

        # Projection + predicate pushdown: read only relevant fields and games.
        frame = lazy.filter(pl.col("game_id").is_in(game_ids)).select(PBP_COLUMNS).collect()
        frames.append(frame)
        print(f"{season}: loaded {frame.height:,} play records from selected games")

    pbp = pl.concat(frames, how="vertical_relaxed").with_columns(
        pl.col("passer_player_id").cast(pl.String)
    )

    missing_game_ids = sorted(set(master["game_id"].to_list()) - set(pbp["game_id"].to_list()))
    if missing_game_ids:
        raise ValueError(f"No PBP records for {len(missing_game_ids)} master games: {missing_game_ids[:5]}")

    if pbp.select(pl.struct("game_id", "play_id").n_unique()).item() != pbp.height:
        raise ValueError("Duplicate (game_id, play_id) entries in the selected PBP records")
    return pbp


def select_passing_attempts(pbp: pl.DataFrame, master: pl.DataFrame) -> pl.DataFrame:
    """Select official-style pass attempts, including clock-stopping QB spikes.

    NFL spikes count as incomplete pass attempts. nflfastR uses a dedicated
    play_type value ("qb_spike"), while dropbacks exclude spikes. Keep those
    statistical definitions separate.
    """
    spike = pl.col("qb_spike").fill_null(0) == 1
    regular_pass = (
        (pl.col("play_type") == "pass")
        & (pl.col("pass_attempt").fill_null(0) == 1)
    )
    spike_pass = (pl.col("play_type") == "qb_spike") & spike

    throws = pbp.filter(
        (regular_pass | spike_pass)
        & (pl.col("sack").fill_null(0) == 0)
        & (pl.col("qb_scramble").fill_null(0) == 0)
        & (pl.col("two_point_attempt").fill_null(0) == 0)
    ).with_columns(
        # Spikes are incomplete passes with no passing yards or touchdowns.
        pl.when(spike).then(pl.lit(0)).otherwise(pl.col("complete_pass")).alias("complete_pass"),
        pl.when(spike).then(pl.lit(0)).otherwise(pl.col("passing_yards")).alias("passing_yards"),
        pl.when(spike).then(pl.lit(0)).otherwise(pl.col("pass_touchdown")).alias("pass_touchdown"),
        pl.when(spike).then(pl.lit(0)).otherwise(pl.col("interception")).alias("interception"),
    )

    # Audit throws without a player identifier. Never guess which QB threw.
    qb_teams = master.select("game_id", "team").unique()
    unidentified = (
        throws.filter(pl.col("passer_player_id").is_null())
        .join(qb_teams, left_on=["game_id", "posteam"], right_on=["game_id", "team"], how="inner")
    )
    if unidentified.height:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        audit_path = OUTPUT_DIR / "unattributed_pass_attempts.csv"
        unidentified.write_csv(audit_path)
        raise ValueError(
            f"Found {unidentified.height} unattributed pass attempts in studied teams. "
            f"Inspect {audit_path}; do not assign them automatically to the starter."
        )

    attempts = (
        throws.rename({"passer_player_id": "player_id", "posteam": "team"})
        .join(master.select("game_id", "player_id", "team"),
              on=["game_id", "player_id", "team"], how="inner")
    )

    # This diagnostic makes the spike inclusion transparent during validation.
    print("\nOfficial-style QB spikes included:")
    spike_rows = attempts.filter(pl.col("qb_spike").fill_null(0) == 1)
    print(spike_rows.select("game_id", "play_id", "player_id", "team", "play_type"))

    null_completions = attempts.filter(pl.col("complete_pass").is_null())
    missing_yards = attempts.filter(
        (pl.col("complete_pass") == 1) & pl.col("passing_yards").is_null()
    )
    if null_completions.height or missing_yards.height:
        raise ValueError(
            "Incomplete passing flags or missing yards on completions: "
            f"{null_completions.height} missing completion indicators, "
            f"{missing_yards.height} completed passes without passing yards."
        )

    return attempts


def aggregate_attempts(attempts: pl.DataFrame, master: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    summary = attempts.group_by("player_id", "game_id").agg(
        pl.len().alias("attempts"),
        pl.col("complete_pass").sum().alias("completions"),
        pl.col("passing_yards").fill_null(0).sum().alias("passing_yards"),
        pl.col("pass_touchdown").fill_null(0).sum().alias("passing_tds"),
        pl.col("interception").fill_null(0).sum().alias("interceptions"),
    )

    # LEFT join keeps all 262 starts, even games with zero attempts.
    full = master.join(summary, on=["player_id", "game_id"], how="left")
    full = full.with_columns(
        [pl.col(c).fill_null(0).cast(pl.Int64) for c in COUNT_COLUMNS]
    ).with_columns(
        pl.when(pl.col("attempts") > 0)
        .then(pl.col("completions") / pl.col("attempts") * 100)
        .otherwise(None).alias("completion_pct"),
        pl.when(pl.col("attempts") > 0)
        .then(pl.col("passing_yards") / pl.col("attempts"))
        .otherwise(None).alias("yards_per_attempt"),
        pl.when(pl.col("attempts") > 0)
        .then(pl.col("passing_tds") / pl.col("attempts") * 100)
        .otherwise(None).alias("td_rate"),
        pl.when(pl.col("attempts") > 0)
        .then(pl.col("interceptions") / pl.col("attempts") * 100)
        .otherwise(None).alias("int_rate"),
    ).sort(["player_name", "start_no"])

    if full.height != 262:
        raise AssertionError(f"Lost or duplicated master records: {full.height}")
    if full.select(pl.struct("player_id", "game_id").n_unique()).item() != 262:
        raise AssertionError("Nonunique quarterback-game pairs after aggregation")
    if full.filter(pl.col("completions") > pl.col("attempts")).height:
        raise AssertionError("Completions exceed pass attempts")
    if full.filter(pl.col("passing_tds") > pl.col("attempts")).height:
        raise AssertionError("Passing TDs exceed pass attempts")
    if full.filter(pl.col("interceptions") > pl.col("attempts")).height:
        raise AssertionError("Interceptions exceed pass attempts")

    game_stats = full.select(
        "player_id", "player_name", "game_id", "start_no", "season", "week",
        *COUNT_COLUMNS, "completion_pct", "yards_per_attempt", "td_rate", "int_rate",
    )
    return game_stats, full


def verify_against_official_records(stats: pl.DataFrame) -> None:
    # NFL.com, Brady's 2005 regular-season Week 17 game log (vs. MIA).
    brady_mia = stats.filter(
        (pl.col("player_name") == "Tom Brady")
        & (pl.col("game_id") == "2005_17_MIA_NE")
    )
    # 3/8, 37 yards, 1 TD, 1 INT. Cassel's passes must NOT be included.
    checks = [
        ("Brady vs. Miami, Jan 1 2006", brady_mia,
         (8, 3, 37, 1, 1)),
        # Chiefs official 2018 season stats (Mahomes started all 16 games).
        ("Mahomes 2018 regular season",
         stats.filter((pl.col("player_name") == "Patrick Mahomes") & (pl.col("season") == 2018)),
         (580, 383, 5097, 50, 12)),
    ]

    for label, data, expected in checks:
        if data.height == 0:
            raise AssertionError(f"Reference sample not found: {label}")
        actual = tuple(int(data[c].sum()) for c in COUNT_COLUMNS)
        print(f"{label}: actual={actual}, reference={expected}")
        if actual != expected:
            raise AssertionError(
                f"Official reference mismatch for {label}. "
                "Investigate missing/incorrect PBP attribution, spikes, "
                "penalties, or stat definitions before exporting results."
            )


def main() -> None:
    master = load_master()
    pbp = load_relevant_plays(master)
    attempts = select_passing_attempts(pbp, master)
    stats, full = aggregate_attempts(attempts, master)

    print("\nPassing totals:")
    print(stats.group_by("player_name").agg([pl.col(c).sum() for c in COUNT_COLUMNS]))
    zero_attempt_games = stats.filter(pl.col("attempts") == 0)
    if zero_attempt_games.height:
        print("\nWARNING: Starts with zero attributed pass attempts:")
        print(zero_attempt_games.select("player_name", "game_id", "start_no"))

    verify_against_official_records(stats)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    attempts.write_parquet(OUTPUT_DIR / "qb_pass_attempts.parquet")
    stats.write_parquet(OUTPUT_DIR / "qb_game_stats.parquet")
    stats.write_csv(OUTPUT_DIR / "qb_game_stats.csv")
    full.write_parquet(OUTPUT_DIR / "qb_master_stats.parquet")
    print("\nVALIDATED: 262 rows. Passing statistics exported successfully.")


if __name__ == "__main__":
    main()
