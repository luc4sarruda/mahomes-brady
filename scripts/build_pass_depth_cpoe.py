"""Build audited pass-depth and CPOE tables for the first-131-start subcohorts.

Run from the repository root:
    python3 scripts/build_pass_depth_cpoe.py

Prerequisites: inspect_pass_depth_cpoe.py in the same scripts directory;
qb_first_131_starts.parquet, qb_game_stats.parquet, and nflverse PBP partitions.
The script reuses the validated official-attempt filters and does not mutate source data.
"""

from pathlib import Path
import math
import polars as pl

from inspect_pass_depth_cpoe import (
    study_starts, load_pass_attempts, verify_official_attempts, add_depth,
    DEPTH_LABELS,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/processed"
REPORTS = ROOT / "reports/validation"
METRICS = [
    "attempts", "completions", "modeled_attempts", "modeled_completions",
    "sum_cp", "sum_cpoe_pp", "epa_attempts", "sum_qb_epa",
]


def enrich_throws(attempts: pl.DataFrame) -> pl.DataFrame:
    """Keep spikes in official totals; never invent depth or completion probability."""
    tagged = add_depth(attempts).with_columns(
        pl.when(pl.col("qb_spike").fill_null(0) == 1)
        .then(pl.lit(0.0))
        .otherwise(pl.col("complete_pass").cast(pl.Float64))
        .alias("completion_flag")
    )
    invalid = tagged.filter(
        pl.col("completion_flag").is_not_null()
        & ~pl.col("completion_flag").is_in([0.0, 1.0])
    )
    if invalid.height:
        raise AssertionError(f"Invalid completion flags: {invalid.height}")
    invalid = tagged.filter(
        pl.col("cp").is_not_null()
        & (~pl.col("cp").is_between(0, 1) | ~pl.col("cp").is_finite())
    )
    if invalid.height:
        raise AssertionError(f"Invalid completion probabilities: {invalid.height}")

    # Modeled CPOE observations must have valid target depth, CP, and result.
    tagged = tagged.with_columns(
        (
            pl.col("depth_zone").is_not_null()
            & pl.col("cp").is_not_null()
            & pl.col("completion_flag").is_not_null()
        ).alias("cpoe_eligible"),
        (
            pl.col("depth_zone").is_not_null()
            & pl.col("qb_epa").is_not_null()
            & pl.col("qb_epa").is_finite()
        ).alias("epa_eligible"),
    ).with_columns(
        pl.when(pl.col("cpoe_eligible"))
        .then(pl.col("cp"))
        .otherwise(None).alias("modeled_cp"),
        pl.when(pl.col("cpoe_eligible"))
        .then(pl.col("completion_flag"))
        .otherwise(None).alias("modeled_completion"),
        pl.when(pl.col("cpoe_eligible"))
        .then(100.0 * (pl.col("completion_flag") - pl.col("cp")))
        .otherwise(None).alias("calculated_cpoe_pp"),
        pl.when(pl.col("epa_eligible"))
        .then(pl.col("qb_epa"))
        .otherwise(None).alias("eligible_qb_epa"),
    )
    # Compare all usable model predictions with stored nflverse CPOE.
    checked = tagged.filter(pl.col("cpoe_eligible"))
    missing_source = checked.filter(pl.col("cpoe").is_null())
    if missing_source.height:
        raise AssertionError(f"{missing_source.height} modeled throws missing source CPOE")
    error = checked.select(
        (pl.col("calculated_cpoe_pp") - pl.col("cpoe"))
        .abs().max().alias("max_error")
    ).item()
    if error is None or not math.isfinite(float(error)) or error > 0.001:
        raise AssertionError(f"CPOE unit/formula mismatch; max abs error={error}")
    # Nothing with a charted depth may have an unknown completion result.
    unknown_completion = tagged.filter(
        pl.col("depth_zone").is_not_null()
        & pl.col("completion_flag").is_null()
    )
    if unknown_completion.height:
        REPORTS.mkdir(parents=True, exist_ok=True)
        unknown_completion.select("game_id", "play_id", "player_name", "season").write_csv(
            REPORTS / "pass_depth_unknown_completions.csv"
        )
        raise AssertionError("Charted attempts missing completion result; review report")
    return tagged


def group_totals(throws: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Aggregate sufficient statistics so per-season and per-game data reconcile."""
    return throws.group_by(keys).agg(
        pl.len().alias("attempts"),
        pl.col("completion_flag").sum().alias("completions"),
        pl.col("cpoe_eligible").sum().alias("modeled_attempts"),
        pl.col("modeled_completion").sum().alias("modeled_completions"),
        pl.col("modeled_cp").sum().alias("sum_cp"),
        pl.col("calculated_cpoe_pp").sum().alias("sum_cpoe_pp"),
        pl.col("epa_eligible").sum().alias("epa_attempts"),
        pl.col("eligible_qb_epa").sum().alias("sum_qb_epa"),
    )


def add_rates(grouped: pl.DataFrame, share_keys: list[str]) -> pl.DataFrame:
    denom = grouped.group_by(share_keys).agg(
        pl.col("attempts").sum().alias("charted_attempts_in_cohort")
    )
    return grouped.join(denom, on=share_keys, how="left").with_columns(
        (100.0 * pl.col("attempts") / pl.col("charted_attempts_in_cohort"))
        .alias("attempt_share_pct"),
        (100.0 * pl.col("completions") / pl.col("attempts"))
        .alias("completion_pct"),
        pl.when(pl.col("modeled_attempts") > 0)
        .then(100.0 * pl.col("modeled_completions") / pl.col("modeled_attempts"))
        .otherwise(None).alias("modeled_completion_pct"),
        pl.when(pl.col("modeled_attempts") > 0)
        .then(100.0 * pl.col("sum_cp") / pl.col("modeled_attempts"))
        .otherwise(None).alias("expected_completion_pct"),
        pl.when(pl.col("modeled_attempts") > 0)
        .then(pl.col("sum_cpoe_pp") / pl.col("modeled_attempts"))
        .otherwise(None).alias("cpoe_pp"),
        (100.0 * pl.col("modeled_attempts") / pl.col("attempts"))
        .alias("cp_coverage_pct"),
        pl.when(pl.col("epa_attempts") > 0)
        .then(pl.col("sum_qb_epa") / pl.col("epa_attempts"))
        .otherwise(None).alias("qb_epa_per_attempt"),
    )


def assert_aggregations(throws: pl.DataFrame, *tables: pl.DataFrame) -> None:
    expected = throws.filter(pl.col("depth_zone").is_not_null()).height
    for table in tables:
        if int(table["attempts"].sum()) != expected:
            raise AssertionError("Attempt count differs between depth tables")
        assert_unique_cols = [
            col for col in ("player_id", "game_id", "season", "depth_zone")
            if col in table.columns
        ]
        if table.select(pl.struct(assert_unique_cols).n_unique()).item() != table.height:
            raise AssertionError("Duplicate summary keys")
        if table.filter(pl.col("modeled_attempts") > pl.col("attempts")).height:
            raise AssertionError("Modeled denominator exceeds official attempts")
        if table.filter(pl.col("epa_attempts") > pl.col("attempts")).height:
            raise AssertionError("EPA denominator exceeds official attempts")
        bad = table.filter(
            (pl.col("cpoe_pp") - (
                pl.col("modeled_completion_pct") - pl.col("expected_completion_pct")
            )).abs() > 1e-8
        )
        if bad.height:
            raise AssertionError("CPOE must equal actual minus expected on identical throws")


def main() -> None:
    study = study_starts()
    attempts = load_pass_attempts(study)
    verify_official_attempts(study, attempts)
    throws = enrich_throws(attempts)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    known = throws.filter(pl.col("depth_zone").is_not_null())
    unknown = throws.filter(pl.col("depth_zone").is_null())
    if unknown.height:
        unknown.select("player_name", "season", "game_id", "play_id", "air_yards").write_csv(
            REPORTS / "pass_depth_uncharted_attempts.csv"
        )
    if known.height / throws.height < 0.995:
        raise AssertionError("Air-yards coverage below 99.5%; inspect missing depth")
    if known.filter(pl.col("cpoe_eligible")).height / known.height < 0.90:
        raise AssertionError("CPOE coverage below 90%; review source and sample")
    if known.filter(pl.col("epa_eligible")).height / known.height < 0.99:
        raise AssertionError("EPA coverage below 99%; review source and sample")

    zone_keys = ["player_id", "player_name", "depth_zone"]
    season_keys = ["player_id", "player_name", "season", "depth_zone"]
    game_keys = ["player_id", "player_name", "season", "start_no", "game_id", "depth_zone"]
    pooled = add_rates(group_totals(known, zone_keys), ["player_id", "player_name"])
    by_season = add_rates(group_totals(known, season_keys), ["player_id", "player_name", "season"])
    by_game = add_rates(group_totals(known, game_keys), ["player_id", "player_name", "season", "start_no", "game_id"])
    assert_aggregations(throws, pooled, by_season, by_game)

    order = pl.DataFrame({"depth_zone": DEPTH_LABELS, "zone_order": list(range(len(DEPTH_LABELS)))})
    pooled = pooled.join(order, on="depth_zone").sort("player_name", "zone_order")
    by_season = by_season.join(order, on="depth_zone").sort("player_name", "season", "zone_order")
    by_game = by_game.join(order, on="depth_zone").sort("player_name", "start_no", "zone_order")

    audit = throws.group_by("player_name", "season").agg(
        pl.len().alias("official_attempts"),
        pl.col("depth_zone").is_not_null().sum().alias("depth_charted"),
        pl.col("cpoe_eligible").sum().alias("modeled_attempts"),
        pl.col("epa_eligible").sum().alias("epa_attempts"),
    ).with_columns(
        (100 * pl.col("depth_charted") / pl.col("official_attempts")).alias("depth_coverage_pct"),
        (100 * pl.col("modeled_attempts") / pl.col("official_attempts")).alias("cp_coverage_official_pct"),
    ).sort("player_name", "season")

    # Validate against the audit produced in the previous phase when present.
    previous = REPORTS / "pass_depth_cpoe_coverage_by_season.csv"
    if previous.exists():
        earlier = pl.read_csv(previous).select(
            "player_name", "season", "official_attempts", "depth_charted",
            pl.col("depth_and_cp_available").alias("modeled_attempts"),
        )
        comparison = earlier.join(
            audit.select("player_name", "season", "official_attempts", "depth_charted", "modeled_attempts"),
            on=["player_name", "season"], how="inner", suffix="_new"
        )
        if comparison.height != earlier.height:
            raise AssertionError("Cannot reconcile all seasons against prior depth audit")
        for col in ("official_attempts", "depth_charted", "modeled_attempts"):
            if comparison.filter(pl.col(col) != pl.col(f"{col}_new")).height:
                raise AssertionError(f"Changed source classification since audit: {col}")

    throws.write_parquet(OUTPUT / "qb_pass_depth_attempts.parquet")
    by_game.write_parquet(OUTPUT / "qb_pass_depth_by_game.parquet")
    by_season.write_parquet(OUTPUT / "qb_pass_depth_by_season.parquet")
    by_season.write_csv(OUTPUT / "qb_pass_depth_by_season.csv")
    pooled.write_parquet(OUTPUT / "qb_pass_depth_summary.parquet")
    pooled.write_csv(OUTPUT / "qb_pass_depth_summary.csv")
    audit.write_csv(REPORTS / "pass_depth_build_quality_summary.csv")

    print("\n=== PASS DEPTH / CPOE BUILD ===")
    print(f"Official throws: {throws.height:,}")
    print(f"Throws with charted depth: {known.height:,}")
    print(f"CPOE-eligible throws: {known.filter(pl.col('cpoe_eligible')).height:,}")
    print(f"EPA-eligible throws: {known.filter(pl.col('epa_eligible')).height:,}")
    with pl.Config(tbl_rows=20, tbl_cols=12):
        print(pooled.select(
            "player_name", "depth_zone", "attempts", "attempt_share_pct",
            "completion_pct", "modeled_attempts", "cp_coverage_pct",
            "expected_completion_pct", "cpoe_pp", "qb_epa_per_attempt"
        ))
    print("\nPASS: Attempt reconciliation, CPOE identity, coverage, and aggregation checks")
    print(f"Files saved in {OUTPUT} and {REPORTS}")


if __name__ == "__main__":
    main()
