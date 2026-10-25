"""Merge validated passing and rushing statistics into one 262-start study table.

Run from the repository root:
    python3 scripts/build_complete_qb_stats.py

Inputs:
    data/processed/qb_first_131_starts.parquet
    data/processed/qb_game_stats.parquet
    data/processed/qb_rushing_stats.parquet

Outputs:
    data/processed/qb_complete_stats.parquet
    data/processed/qb_complete_stats.csv

This step does not modify raw data or compute era-adjusted metrics.
"""

from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
MASTER_PATH = DATA_DIR / "qb_first_131_starts.parquet"
PASSING_PATH = DATA_DIR / "qb_game_stats.parquet"
RUSHING_PATH = DATA_DIR / "qb_rushing_stats.parquet"
OUTPUT_STEM = DATA_DIR / "qb_complete_stats"

KEYS = ["player_id", "game_id"]
IDENTITY = KEYS + ["player_name", "season", "week", "start_no"]
PASSING_COUNTS = [
    "attempts", "completions", "passing_yards", "passing_tds", "interceptions"
]
RUSHING_COUNTS = [
    "carries", "rushing_yards", "rushing_tds", "scrambles", "scramble_yards",
    "designed_runs", "designed_run_yards",
    "aborted_rushes", "aborted_rush_yards", "kneels", "kneel_yards",
    "non_kneel_carries", "non_kneel_yards", "sacks_taken", "sack_yards_lost"
]
NONNEGATIVE_COUNTS = [
    "attempts", "completions", "passing_yards", "passing_tds", "interceptions",
    "carries", "rushing_tds", "scrambles", "designed_runs",
    "aborted_rushes", "kneels",
    "non_kneel_carries", "sacks_taken", "sack_yards_lost"
]


def read_table(path: Path, label: str, required: list[str]) -> pl.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    df = pl.read_parquet(path).with_columns(pl.col("player_id").cast(pl.String))
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f"{label} missing columns: {sorted(missing)}")
    if df.height != 262:
        raise AssertionError(f"{label} must have 262 rows, found {df.height}")
    if df.select(pl.struct(KEYS).n_unique()).item() != 262:
        raise AssertionError(f"{label} has duplicate (player_id, game_id) pairs")
    if df.filter(pl.any_horizontal(*[pl.col(k).is_null() for k in KEYS])).height:
        raise AssertionError(f"{label} has null join keys")
    return df


def assert_same_sample(master: pl.DataFrame, other: pl.DataFrame, label: str) -> None:
    master_keys = master.select(KEYS)
    other_keys = other.select(KEYS)
    missing = master_keys.join(other_keys, on=KEYS, how="anti")
    unexpected = other_keys.join(master_keys, on=KEYS, how="anti")
    if missing.height or unexpected.height:
        raise AssertionError(
            f"{label}: sample keys differ from master. "
            f"Missing={missing.height}, unexpected={unexpected.height}"
        )

    # The row grain is QB x game. Metadata must match across pipelines.
    expected = master.select(IDENTITY).sort(KEYS)
    observed = other.select(IDENTITY).sort(KEYS)
    if not expected.equals(observed, null_equal=True):
        raise AssertionError(
            f"{label}: player_name, season, week, or start_no differs from master"
        )


def build_complete_table() -> pl.DataFrame:
    master = read_table(MASTER_PATH, "Master starts", IDENTITY)
    passing = read_table(PASSING_PATH, "Passing stats", IDENTITY + PASSING_COUNTS)
    rushing = read_table(RUSHING_PATH, "Rushing stats", IDENTITY + RUSHING_COUNTS)

    assert_same_sample(master, passing, "Passing stats")
    assert_same_sample(master, rushing, "Rushing stats")

    if any(c in master.columns for c in PASSING_COUNTS + RUSHING_COUNTS):
        raise AssertionError("Master table already contains individual stat columns")

    complete = (
        master
        .join(passing.select(KEYS + PASSING_COUNTS), on=KEYS, how="left", validate="1:1")
        .join(rushing.select(KEYS + RUSHING_COUNTS), on=KEYS, how="left", validate="1:1")
    )

    if complete.height != 262:
        raise AssertionError(f"Expected exactly 262 records; got {complete.height}")

    all_counts = PASSING_COUNTS + RUSHING_COUNTS
    incomplete = complete.filter(pl.any_horizontal(*[pl.col(c).is_null() for c in all_counts]))
    if incomplete.height:
        raise AssertionError(f"{incomplete.height} rows have missing aggregate stats")

    invalid = complete.filter(pl.any_horizontal(*[pl.col(c) < 0 for c in NONNEGATIVE_COUNTS]))
    if invalid.height:
        raise AssertionError(f"{invalid.height} rows have invalid negative count values")

    if complete.filter(pl.col("completions") > pl.col("attempts")).height:
        raise AssertionError("Completions exceed passing attempts")
    if complete.filter(pl.col("rushing_tds") > pl.col("carries")).height:
        raise AssertionError("Rushing TDs exceed carries")
    # The validated rushing pipeline separates aborted snaps from designed runs.
    # These are mutually exclusive categories, and every rushing attempt must
    # belong to exactly one of them. Do not drop aborted rushes in the merge.
    bad_rush_partition = complete.filter(
        (pl.col("carries") != (
            pl.col("scrambles") + pl.col("designed_runs")
            + pl.col("aborted_rushes") + pl.col("kneels")
        ))
        | (pl.col("rushing_yards") != (
            pl.col("scramble_yards") + pl.col("designed_run_yards")
            + pl.col("aborted_rush_yards") + pl.col("kneel_yards")
        ))
        | (pl.col("non_kneel_carries") != pl.col("carries") - pl.col("kneels"))
        | (pl.col("non_kneel_yards") != pl.col("rushing_yards") - pl.col("kneel_yards"))
        | (pl.col("non_kneel_carries") != (
            pl.col("scrambles") + pl.col("designed_runs")
            + pl.col("aborted_rushes")
        ))
    )
    if bad_rush_partition.height:
        diagnostic_columns = [
            "player_name", "game_id", "start_no", "carries", "rushing_yards",
            "scrambles", "scramble_yards", "designed_runs", "designed_run_yards",
            "aborted_rushes", "aborted_rush_yards", "kneels", "kneel_yards",
            "non_kneel_carries", "non_kneel_yards",
        ]
        print("Rushing partition failures (first 10 rows):")
        print(bad_rush_partition.select(diagnostic_columns).head(10))
        raise AssertionError(
            f"Rushing partition check failed in {bad_rush_partition.height} QB-game rows"
        )

    # Recompute all derived rates from integer totals. Null means no attempts.
    complete = complete.with_columns(
        pl.when(pl.col("attempts") > 0)
        .then(100 * pl.col("completions") / pl.col("attempts"))
        .otherwise(None).alias("completion_pct"),
        pl.when(pl.col("attempts") > 0)
        .then(pl.col("passing_yards") / pl.col("attempts"))
        .otherwise(None).alias("yards_per_attempt"),
        pl.when(pl.col("attempts") > 0)
        .then(100 * pl.col("passing_tds") / pl.col("attempts"))
        .otherwise(None).alias("td_rate"),
        pl.when(pl.col("attempts") > 0)
        .then(100 * pl.col("interceptions") / pl.col("attempts"))
        .otherwise(None).alias("int_rate"),
        pl.when(pl.col("carries") > 0)
        .then(pl.col("rushing_yards") / pl.col("carries"))
        .otherwise(None).alias("yards_per_carry"),
        pl.when(pl.col("non_kneel_carries") > 0)
        .then(pl.col("non_kneel_yards") / pl.col("non_kneel_carries"))
        .otherwise(None).alias("yards_per_non_kneel_carry"),
    ).sort(["player_name", "start_no"])

    for name, group in complete.group_by("player_name"):
        if group.height != 131 or sorted(group["start_no"].to_list()) != list(range(1, 132)):
            raise AssertionError(f"Invalid start sequence for {name}")
        wins = group.filter(pl.col("result") == "W").height
        losses = group.filter(pl.col("result") == "L").height
        ties = group.filter(pl.col("result") == "T").height
        if (wins, losses, ties) != (100, 31, 0):
            raise AssertionError(f"Unexpected starter record for {name}: {wins}-{losses}-{ties}")
        print(f"{name}: 131 starts, record 100-31-0, stats integrated")

    return complete


def main() -> None:
    complete = build_complete_table()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    complete.write_parquet(OUTPUT_STEM.with_suffix(".parquet"))
    complete.write_csv(OUTPUT_STEM.with_suffix(".csv"))
    print(f"\nSUCCESS: {complete.height} rows and {complete.width} columns")
    print(f"Saved: {OUTPUT_STEM.with_suffix('.parquet')}")
    print(f"Saved: {OUTPUT_STEM.with_suffix('.csv')}")


if __name__ == "__main__":
    main()
