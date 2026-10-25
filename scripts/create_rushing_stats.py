"""Build QB rushing, mobility, and sacks data from the 262-start study sample.

Run from repository root:
    python3 scripts/create_rushing_stats.py

Inputs:
    data/processed/qb_first_131_starts.parquet
    data/raw/play_by_play/pbp_{season}.parquet

Outputs (only after local integrity checks pass):
    data/processed/qb_rushing_plays.parquet
    data/processed/qb_sack_plays.parquet
    data/processed/qb_rushing_stats.parquet
    data/processed/qb_rushing_stats.csv

IMPORTANT: PBP-derived statistics are provisional until audited against the
nflverse weekly player statistics and a sample of independent NFL box scores.
"""

from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "data/processed/qb_first_131_starts.parquet"
PBP_DIR = ROOT / "data/raw/play_by_play"
OUTPUT_DIR = ROOT / "data/processed"

PBP_FIELDS = [
    "game_id", "play_id", "posteam", "season_type", "play_type", "desc",
    "rusher_player_id", "passer_player_id", "rush_attempt", "rushing_yards",
    "rush_touchdown", "qb_scramble", "qb_kneel", "two_point_attempt",
    "sack", "yards_gained", "td_player_id",
]
COUNT_FIELDS = [
    "carries", "rushing_yards", "rushing_tds", "scrambles", "scramble_yards",
    "designed_runs", "designed_run_yards", "aborted_rushes", "aborted_rush_yards",
    "kneels", "kneel_yards",
    "non_kneel_carries", "non_kneel_yards", "sacks_taken", "sack_yards_lost",
]

# Some historical PBP plays are kneels even when qb_kneel is set to zero.
# A conservative description-based fallback is audited in the detail table.
KNEEL_PATTERN = r"(?i)\b(?:kneels?|kneeled|knelt|takes? (?:a )?knee|took (?:a )?knee)\b"
ABORTED_PATTERN = r"(?i)\baborted\b"

# Verified NFL box-score exception. nflverse credits the aborted snap as
# a zero-yard run in this player's PBP row, but NFL credits +1 rushing yard.
# Do not apply this correction unless the raw row still matches its known values.
ABORTED_SNAP_GAME = "2023_02_KC_JAX"
ABORTED_SNAP_QB = "00-0033873"


def load_master() -> pl.DataFrame:
    if not MASTER_PATH.is_file():
        raise FileNotFoundError(f"Master table not found: {MASTER_PATH}")
    master = pl.read_parquet(MASTER_PATH).with_columns(
        pl.col("player_id").cast(pl.String)
    )
    required = {"player_id", "player_name", "game_id", "team", "season", "start_no"}
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"Master table missing columns: {sorted(missing)}")
    if master.height != 262:
        raise AssertionError(f"Expected 262 starts; found {master.height}")
    if master.select(pl.struct("player_id", "game_id").n_unique()).item() != 262:
        raise AssertionError("Duplicate player-game pairs in the master table")
    return master


def load_study_pbp(master: pl.DataFrame) -> pl.DataFrame:
    frames = []
    for season in sorted(master["season"].unique().to_list()):
        path = PBP_DIR / f"pbp_{season}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Play-by-play file not found: {path}")

        game_ids = master.filter(pl.col("season") == season)["game_id"].to_list()
        lazy = pl.scan_parquet(path)
        missing = set(PBP_FIELDS) - set(lazy.collect_schema().names())
        if missing:
            raise ValueError(f"PBP {season} missing required columns: {sorted(missing)}")

        frame = (
            lazy.filter(pl.col("game_id").is_in(game_ids))
            .select(PBP_FIELDS)
            .collect()
        )
        print(f"{season}: {frame.height:,} play records loaded")
        frames.append(frame)

    pbp = pl.concat(frames, how="vertical_relaxed").with_columns(
        pl.col("rusher_player_id").cast(pl.String),
        pl.col("passer_player_id").cast(pl.String),
        pl.col("td_player_id").cast(pl.String),
    )
    if pbp.select(pl.struct("game_id", "play_id").n_unique()).item() != pbp.height:
        raise AssertionError("Duplicate game_id / play_id records in PBP")
    missing_games = set(master["game_id"].to_list()) - set(pbp["game_id"].to_list())
    if missing_games:
        raise AssertionError(f"Missing PBP for {len(missing_games)} starts: {sorted(missing_games)[:5]}")
    return pbp.filter(pl.col("season_type") == "REG")


def classify_rushes(pbp: pl.DataFrame, master: pl.DataFrame) -> pl.DataFrame:
    # A kneel can appear as qb_kneel, as a play type, or only in the
    # description in older seasons. Never classify it as a designed run.
    rushes = (
        pbp.with_columns(
            (
                (pl.col("qb_kneel").fill_null(0) == 1)
                | (pl.col("play_type") == "qb_kneel")
                | pl.col("desc").fill_null("").str.contains(KNEEL_PATTERN)
            ).alias("is_kneel"),
        )
        .filter(
            (pl.col("two_point_attempt").fill_null(0) == 0)
            & (
                ((pl.col("rush_attempt").fill_null(0) == 1)
                 & pl.col("play_type").is_in(["run", "qb_kneel"]))
                | (pl.col("is_kneel") & pl.col("play_type").is_in(["run", "qb_kneel"]))
            )
        )
    )

    # A record without a rusher ID cannot be attributed safely to the QB.
    # Audit any unassigned knee (possibly the backup QB) instead of guessing.
    suspicious = rushes.filter(pl.col("is_kneel") & pl.col("rusher_player_id").is_null()).join(
        master.select("game_id", "team").unique(),
        left_on=["game_id", "posteam"], right_on=["game_id", "team"], how="inner",
    )
    if suspicious.height:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        audit = OUTPUT_DIR / "unattributed_kneels.csv"
        suspicious.select("game_id", "play_id", "posteam", "desc").write_csv(audit)
        raise ValueError(
            f"Found {suspicious.height} unattributed kneels on studied teams. "
            f"Review {audit} before assigning rushing statistics."
        )

    # Match the participant's ID AND the offense's team; do not assign a
    # substitute's rushes to the starter (e.g., Brady/Cassel 2005).
    selected = (
        rushes.rename({"rusher_player_id": "player_id", "posteam": "team"})
        .join(master.select("game_id", "player_id", "team"),
              on=["game_id", "player_id", "team"], how="inner")
        .with_columns(
            ((pl.col("qb_scramble").fill_null(0) == 1) & ~pl.col("is_kneel"))
            .alias("is_scramble"),
            (pl.col("desc").fill_null("").str.contains(ABORTED_PATTERN)
             & (pl.col("is_kneel") == False)
             & (pl.col("qb_scramble").fill_null(0) != 1))
            .alias("is_aborted"),
        )
        .with_columns(
            (~pl.col("is_kneel") & ~pl.col("is_scramble") & ~pl.col("is_aborted"))
            .alias("is_designed_run")
        )
    )

    # rush_touchdown is PLAY-level (a lateral receiver can score).
    # Only count a QB rushing touchdown when the scorer's GSIS ID matches.
    scoring = selected.filter(pl.col("rush_touchdown") == 1)
    if scoring.filter(pl.col("td_player_id").is_null()).height:
        raise ValueError(
            "Some QB rush plays ended in a touchdown without td_player_id. "
            "Inspect attribution instead of assuming the initial rusher scored."
        )
    selected = selected.with_columns(
        ((pl.col("rush_touchdown") == 1) &
         (pl.col("td_player_id") == pl.col("player_id"))).alias("credited_rushing_td"),
        pl.col("rushing_yards").alias("source_rushing_yards"),
        pl.lit(None, dtype=pl.String).alias("correction_reason"),
    )

    # 2023 Week 2: the aborted-snap recovery gained one official QB rushing
    # yard. A guarded one-row correction keeps the raw measurement available.
    correction = (
        (pl.col("game_id") == ABORTED_SNAP_GAME)
        & (pl.col("player_id") == ABORTED_SNAP_QB)
        & pl.col("is_aborted")
    )
    affected = selected.filter(correction)
    if affected.height != 1:
        raise ValueError(
            f"Expected exactly one Mahomes aborted-snap rush in "
            f"{ABORTED_SNAP_GAME}, found {affected.height}; inspect the source."
        )
    row = affected.row(0, named=True)
    if int(row["source_rushing_yards"]) != 0 or int(row["yards_gained"]) != 1:
        raise ValueError(
            "The 2023 aborted-snap source fields have changed; "
            f"expected rushing_yards=0 and yards_gained=1, got "
            f"{row['source_rushing_yards']} and {row['yards_gained']}. "
            "Do not apply a stale correction."
        )
    selected = selected.with_columns(
        pl.when(correction).then(pl.col("yards_gained"))
          .otherwise(pl.col("rushing_yards")).alias("rushing_yards"),
        pl.when(correction).then(pl.lit("DQ-005: aborted-snap QB rushing yard"))
          .otherwise(pl.col("correction_reason")).alias("correction_reason"),
    )
    print(
        f"2020 lateral TD attribution: player-specific scorer field enabled. "
        f"2023 aborted-snap correction: {row['game_id']} play {row['play_id']}."
    )

    if selected.filter(pl.col("rushing_yards").is_null()).height:
        raise ValueError("Missing rushing_yards on credited QB rushes; do not replace with zero")
    if selected.filter(pl.col("rush_touchdown").is_null()).height:
        raise ValueError("Missing rush_touchdown flags on credited QB rushes")
    if selected.filter(pl.col("is_kneel") & (pl.col("rush_touchdown") == 1)).height:
        raise ValueError("Kneel-down unexpectedly labeled as a rushing touchdown")
    return selected


def select_sacks(pbp: pl.DataFrame, master: pl.DataFrame) -> pl.DataFrame:
    sack_plays = pbp.filter(
        (pl.col("sack").fill_null(0) == 1)
        & (pl.col("two_point_attempt").fill_null(0) == 0)
        & (pl.col("play_type") == "pass")
    )
    missing_qb = sack_plays.filter(pl.col("passer_player_id").is_null()).join(
        master.select("game_id", "team").unique(),
        left_on=["game_id", "posteam"], right_on=["game_id", "team"], how="inner",
    )
    if missing_qb.height:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        audit = OUTPUT_DIR / "unattributed_sacks.csv"
        missing_qb.select("game_id", "play_id", "posteam", "desc").write_csv(audit)
        raise ValueError(f"{missing_qb.height} sacks have no QB ID. Review {audit}")

    selected = (
        sack_plays.rename({"passer_player_id": "player_id", "posteam": "team"})
        .join(master.select("game_id", "player_id", "team"),
              on=["game_id", "player_id", "team"], how="inner")
    )
    if selected.filter(pl.col("yards_gained").is_null()).height:
        raise ValueError("Missing yards_gained on QB sack records")
    if selected.filter(pl.col("yards_gained") > 0).height:
        raise ValueError("Unexpected positive yards gained on a sack; inspect records")
    return selected


def aggregate(master: pl.DataFrame, rushes: pl.DataFrame, sacks: pl.DataFrame) -> pl.DataFrame:
    rush_summary = rushes.group_by("game_id", "player_id").agg(
        pl.len().alias("carries"),
        pl.col("rushing_yards").sum().alias("rushing_yards"),
        pl.col("credited_rushing_td").sum().alias("rushing_tds"),
        pl.col("is_scramble").sum().alias("scrambles"),
        pl.col("rushing_yards").filter(pl.col("is_scramble")).sum().alias("scramble_yards"),
        pl.col("is_designed_run").sum().alias("designed_runs"),
        pl.col("rushing_yards").filter(pl.col("is_designed_run")).sum().alias("designed_run_yards"),
        pl.col("is_aborted").sum().alias("aborted_rushes"),
        pl.col("rushing_yards").filter(pl.col("is_aborted")).sum().alias("aborted_rush_yards"),
        pl.col("is_kneel").sum().alias("kneels"),
        pl.col("rushing_yards").filter(pl.col("is_kneel")).sum().alias("kneel_yards"),
    )
    sack_summary = sacks.group_by("game_id", "player_id").agg(
        pl.len().alias("sacks_taken"),
        (-pl.col("yards_gained").sum()).alias("sack_yards_lost"),
    )
    full = (
        master.join(rush_summary, on=["game_id", "player_id"], how="left")
        .join(sack_summary, on=["game_id", "player_id"], how="left")
        .with_columns(
            (pl.col("carries").fill_null(0) - pl.col("kneels").fill_null(0)).alias("non_kneel_carries"),
            (pl.col("rushing_yards").fill_null(0) - pl.col("kneel_yards").fill_null(0)).alias("non_kneel_yards"),
        )
        .with_columns([pl.col(c).fill_null(0).cast(pl.Int64) for c in COUNT_FIELDS])
        .with_columns(
            pl.when(pl.col("carries") > 0)
            .then(pl.col("rushing_yards") / pl.col("carries"))
            .otherwise(None).alias("yards_per_carry"),
            pl.when(pl.col("non_kneel_carries") > 0)
            .then(pl.col("non_kneel_yards") / pl.col("non_kneel_carries"))
            .otherwise(None).alias("yards_per_non_kneel_carry"),
        )
        .sort(["player_name", "start_no"])
    )
    if full.height != 262 or full.select(pl.struct("player_id", "game_id").n_unique()).item() != 262:
        raise AssertionError("Aggregation must preserve exactly 262 unique player-game rows")
    bad_partition = full.filter(
        (pl.col("carries") != pl.col("scrambles") + pl.col("designed_runs") + pl.col("aborted_rushes") + pl.col("kneels"))
        | (pl.col("rushing_yards") != pl.col("scramble_yards") + pl.col("designed_run_yards") + pl.col("aborted_rush_yards") + pl.col("kneel_yards"))
        | (pl.col("non_kneel_carries") != pl.col("scrambles") + pl.col("designed_runs") + pl.col("aborted_rushes"))
    )
    if bad_partition.height:
        raise AssertionError("Rushes/yards do not partition into scramble, designed, and kneel categories")
    if full.filter(pl.col("rushing_tds") > pl.col("carries")).height:
        raise AssertionError("Rushing TDs exceed rushing attempts")
    if full.filter((pl.col("carries") < 0) | (pl.col("sacks_taken") < 0)).height:
        raise AssertionError("Negative count values")
    return full.select(
        "player_id", "player_name", "game_id", "season", "week", "start_no",
        *COUNT_FIELDS, "yards_per_carry", "yards_per_non_kneel_carry",
    )


def main() -> None:
    master = load_master()
    pbp = load_study_pbp(master)
    rushes = classify_rushes(pbp, master)
    sacks = select_sacks(pbp, master)
    stats = aggregate(master, rushes, sacks)

    print("\n=== QB RUSHING / MOBILITY / SACKS (PROVISIONAL) ===")
    print(stats.group_by("player_name").agg(
        *[pl.col(col).sum().alias(col) for col in
          ("carries", "rushing_yards", "rushing_tds", "scrambles", "kneels", "sacks_taken")]
    ).sort("player_name"))
    print("All 262 starts preserved; local integrity checks passed.")
    print("NEXT: run validate_rushing_stats.py against nflverse weekly statistics.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rushes.write_parquet(OUTPUT_DIR / "qb_rushing_plays.parquet")
    sacks.write_parquet(OUTPUT_DIR / "qb_sack_plays.parquet")
    stats.write_parquet(OUTPUT_DIR / "qb_rushing_stats.parquet")
    stats.write_csv(OUTPUT_DIR / "qb_rushing_stats.csv")
    print(f"Files saved in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
