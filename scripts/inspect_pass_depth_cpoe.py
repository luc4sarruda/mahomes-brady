"""Audit pass-depth and CPOE coverage for preselected study career windows.

Run from repository root:
    python3 scripts/inspect_pass_depth_cpoe.py

Read-only: does not modify the previously validated passing or EPA tables.
The scope is the first-131-start master table, restricted to Brady 2006-2010
and Mahomes 2018-2021. It is NOT a full-season comparison for Brady 2010.
"""

from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/processed/qb_first_131_starts.parquet"
GAME_STATS = ROOT / "data/processed/qb_game_stats.parquet"
PBP = ROOT / "data/raw/play_by_play"
REPORTS = ROOT / "reports/validation"

WINDOWS = {"Tom Brady": (2006, 2010), "Patrick Mahomes": (2018, 2021)}
REQUIRED = {
    "game_id", "play_id", "posteam", "passer_player_id", "play_type",
    "pass_attempt", "sack", "qb_scramble", "qb_spike", "two_point_attempt",
    "air_yards", "complete_pass", "cp", "cpoe", "qb_epa",
}
DEPTH_LABELS = ["Behind LOS", "0–5", "6–10", "11–19", "20+"]


def study_starts() -> pl.DataFrame:
    master = pl.read_parquet(MASTER)
    columns = {"player_id", "player_name", "game_id", "season", "team", "start_no"}
    if not columns.issubset(master.columns):
        raise ValueError(f"Missing study columns: {sorted(columns - set(master.columns))}")
    study = master.filter(
        ((pl.col("player_name") == "Tom Brady") & pl.col("season").is_between(2006, 2010))
        | ((pl.col("player_name") == "Patrick Mahomes") & pl.col("season").is_between(2018, 2021))
    ).select(sorted(columns)).with_columns(pl.col("player_id").cast(pl.String))
    if study.select(pl.struct("player_id", "game_id").n_unique()).item() != study.height:
        raise AssertionError("Duplicate quarterback starts")
    for name, (first, last) in WINDOWS.items():
        subset = study.filter(pl.col("player_name") == name)
        print(f"{name}: {subset.height} first-131 starts from {first} through {last}")
        if subset.height == 0:
            raise AssertionError(f"No starts for {name}")
    return study


def load_pass_attempts(study: pl.DataFrame) -> pl.DataFrame:
    frames = []
    for season in sorted(study["season"].unique().to_list()):
        path = PBP / f"pbp_{season}.parquet"
        if not path.is_file():
            raise FileNotFoundError(path)
        lazy = pl.scan_parquet(path)
        fields = set(lazy.collect_schema().names())
        missing = REQUIRED - fields
        if missing:
            raise ValueError(f"Season {season} missing PBP fields: {sorted(missing)}")
        ids = study.filter(pl.col("season") == season)["game_id"].to_list()
        frame = lazy.filter(pl.col("game_id").is_in(ids)).select(sorted(REQUIRED)).collect()
        frames.append(frame)
        print(f"{season}: {len(ids)} study games, {frame.height:,} play records")
    raw = pl.concat(frames, how="vertical_relaxed").with_columns(
        pl.col("passer_player_id").cast(pl.String),
    )
    if raw.select(pl.struct("game_id", "play_id").n_unique()).item() != raw.height:
        raise AssertionError("Duplicate PBP game/play IDs")
    if not set(study["game_id"].to_list()).issubset(set(raw["game_id"].to_list())):
        raise AssertionError("One or more study games missing from PBP")

    # Preserve the official-attempt universe, including spikes, for coverage checks.
    spike = pl.col("qb_spike").fill_null(0) == 1
    regular_pass = (
        (pl.col("play_type") == "pass")
        & (pl.col("pass_attempt").fill_null(0) == 1)
    )
    spike_pass = (pl.col("play_type") == "qb_spike") & spike
    attempts = raw.filter(
        (regular_pass | spike_pass)
        & (pl.col("sack").fill_null(0) == 0)
        & (pl.col("qb_scramble").fill_null(0) == 0)
        & (pl.col("two_point_attempt").fill_null(0) == 0)
    )
    relevant_teams = study.select("game_id", "team").unique()
    unknown = attempts.filter(pl.col("passer_player_id").is_null()).join(
        relevant_teams, left_on=["game_id", "posteam"],
        right_on=["game_id", "team"], how="inner"
    )
    if unknown.height:
        REPORTS.mkdir(parents=True, exist_ok=True)
        unknown.write_csv(REPORTS / "pass_depth_unattributed_attempts.csv")
        raise AssertionError(f"{unknown.height} pass attempts lack passer ID for study teams")

    joined = attempts.rename({"posteam": "team", "passer_player_id": "player_id"}).join(
        study, on=["game_id", "player_id", "team"], how="inner"
    )
    if joined.height == 0:
        raise AssertionError("No study QB pass attempts matched")
    return joined


def verify_official_attempts(study: pl.DataFrame, attempts: pl.DataFrame) -> None:
    if not GAME_STATS.exists():
        raise FileNotFoundError(
            f"{GAME_STATS} is needed to reconcile with the validated passing stats"
        )
    official = pl.read_parquet(GAME_STATS).select(
        "player_id", "game_id", pl.col("attempts").alias("official_attempts")
    ).with_columns(pl.col("player_id").cast(pl.String))
    counts = attempts.group_by("player_id", "game_id").agg(
        pl.len().alias("observed_attempts")
    )
    checks = study.select("player_id", "game_id").join(
        official, on=["player_id", "game_id"], how="left"
    ).join(counts, on=["player_id", "game_id"], how="left").with_columns(
        pl.col("observed_attempts").fill_null(0)
    )
    mismatch = checks.filter(
        pl.col("official_attempts").is_null()
        | (pl.col("official_attempts") != pl.col("observed_attempts"))
    )
    if mismatch.height:
        REPORTS.mkdir(parents=True, exist_ok=True)
        mismatch.write_csv(REPORTS / "pass_depth_attempt_mismatches.csv")
        raise AssertionError(
            f"Pass-attempt reconciliation failed for {mismatch.height} games. "
            "Do not proceed until the selection rules match create_player_stats.py."
        )


def add_depth(attempts: pl.DataFrame) -> pl.DataFrame:
    return attempts.with_columns(
        pl.when(pl.col("air_yards").is_null()).then(pl.lit(None, dtype=pl.String))
        .when(pl.col("air_yards") < 0).then(pl.lit("Behind LOS"))
        .when(pl.col("air_yards") < 6).then(pl.lit("0–5"))
        .when(pl.col("air_yards") < 11).then(pl.lit("6–10"))
        .when(pl.col("air_yards") < 20).then(pl.lit("11–19"))
        .otherwise(pl.lit("20+"))
        .alias("depth_zone")
    )


def main() -> None:
    study = study_starts()
    attempts = add_depth(load_pass_attempts(study))
    verify_official_attempts(study, attempts)
    REPORTS.mkdir(parents=True, exist_ok=True)

    invalid = attempts.filter(
        pl.col("cp").is_not_null() & ~pl.col("cp").is_between(0, 1)
    )
    if invalid.height:
        raise AssertionError(f"Completion probability outside [0,1]: {invalid.height} rows")

    eligible = attempts.filter(pl.col("depth_zone").is_not_null())
    coverage = attempts.group_by("player_name", "season").agg(
        pl.len().alias("official_attempts"),
        pl.col("depth_zone").is_not_null().sum().alias("depth_charted"),
        pl.col("cp").is_not_null().sum().alias("cp_available_all"),
        (pl.col("depth_zone").is_not_null() & pl.col("cp").is_not_null()
         & pl.col("complete_pass").is_not_null()).sum().alias("depth_and_cp_available"),
        (pl.col("depth_zone").is_not_null() & pl.col("cpoe").is_not_null())
        .sum().alias("depth_and_cpoe_available"),
        (pl.col("depth_zone").is_not_null() & pl.col("qb_epa").is_not_null())
        .sum().alias("depth_and_epa_available"),
    ).with_columns(
        (100 * pl.col("depth_charted") / pl.col("official_attempts"))
        .alias("air_yards_coverage_pct"),
        (100 * pl.col("depth_and_cp_available") / pl.col("depth_charted"))
        .alias("cp_coverage_among_charted_pct"),
    ).sort("player_name", "season")

    zonal = eligible.group_by("player_name", "season", "depth_zone").agg(
        pl.len().alias("attempts"),
        pl.col("complete_pass").sum().alias("completions"),
        pl.col("cp").is_not_null().sum().alias("cp_available"),
        pl.col("cpoe").is_not_null().sum().alias("cpoe_available"),
        pl.col("qb_epa").is_not_null().sum().alias("qb_epa_available"),
        pl.col("cp").mean().alias("mean_cp"),
        pl.col("cpoe").mean().alias("mean_recorded_cpoe"),
    ).sort("player_name", "season", "depth_zone")

    # Check the scale of the saved CPOE field without assuming 0-1 vs pp.
    cpoe_check = attempts.filter(
        pl.col("cp").is_not_null() & pl.col("cpoe").is_not_null()
        & pl.col("complete_pass").is_not_null()
    ).select(
        pl.len().alias("tested_throws"),
        (pl.col("cpoe") - (pl.col("complete_pass") - pl.col("cp")) * 100)
        .abs().mean().alias("avg_error_if_percentage_points"),
        (pl.col("cpoe") - (pl.col("complete_pass") - pl.col("cp")))
        .abs().mean().alias("avg_error_if_fraction"),
    )

    coverage.write_csv(REPORTS / "pass_depth_cpoe_coverage_by_season.csv")
    zonal.write_csv(REPORTS / "pass_depth_cpoe_zone_audit.csv")
    cpoe_check.write_csv(REPORTS / "pass_depth_cpoe_unit_check.csv")

    print("\n=== PASS-DEPTH / CPOE COVERAGE ===")
    with pl.Config(tbl_rows=25, tbl_cols=10):
        print(coverage)
    print("\n=== CPOE UNIT CROSS-CHECK ===")
    print(cpoe_check)
    print("\nSaved validation reports in:", REPORTS)
    print("NOTE: Do not interpret CPOE until coverage and model units have been checked.")


if __name__ == "__main__":
    main()
