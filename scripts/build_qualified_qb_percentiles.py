"""Build season-specific distributions of qualified NFL QB EPA per dropback.

Usage, from the repository root:
    python3 scripts/build_qualified_qb_percentiles.py

The script REUSES exactly the corrected dropback filter, quarterback-ID
resolution, and baseline reconciliation from the validated EPA pipeline.
It does not modify any previously validated dataset.

Primary qualification: >= 200 usable dropbacks in a completed regular season.
For partial 2026: ceil(200 * league games through study date / 272).
Sensitivity thresholds: 150 and 250, prorated the same way for 2026.

Full-season percentiles can include starts outside the 131-start research
sample (e.g., Brady 2010); strict study-aligned percentiles are reported
ONLY when the complete seasonal QB EPA total matches the study subset.
"""
from __future__ import annotations

import math
from pathlib import Path

import polars as pl

from build_nfl_epa_baselines import load_eligible_dropbacks, load_study
from build_qb_era_adjusted_stats import read_baselines, verify_season_baseline

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports" / "validation"

STUDY_SEASON_PATH = PROCESSED / "qb_study_season_era_summary.parquet"
ALL_PARQUET = PROCESSED / "nfl_qb_season_epa_all.parquet"
ALL_CSV = PROCESSED / "nfl_qb_season_epa_all.csv"
QUAL_PARQUET = PROCESSED / "nfl_qualified_qb_season_epa.parquet"
QUAL_CSV = PROCESSED / "nfl_qualified_qb_season_epa.csv"
STUDY_PARQUET = PROCESSED / "study_qb_qualified_percentiles.parquet"
STUDY_CSV = PROCESSED / "study_qb_qualified_percentiles.csv"
SENSITIVITY_CSV = REPORTS / "qualified_qb_threshold_sensitivity.csv"
AUDIT_CSV = REPORTS / "qualified_qb_percentiles_audit.csv"

PRIMARY_MIN_DB = 200
SENSITIVITY_MIN_DB = (150, 200, 250)
EXPECTED_2026_FULL_GAMES = 272


def minimum_dropbacks(base: int, season: int, league_games: int) -> int:
    """Prorate an explicitly study-defined qualification cutoff for partial 2026."""
    if season == 2026:
        if not (0 < league_games <= EXPECTED_2026_FULL_GAMES):
            raise AssertionError(f"2026: implausible league game count: {league_games}")
        return math.ceil(base * league_games / EXPECTED_2026_FULL_GAMES)
    return base


def assert_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-6):
        raise AssertionError(f"{label}: observed={actual}, expected={expected}")


def rankings_for_season(records: list[dict], minimum: int) -> list[dict]:
    """Rank eligible full-season QB mean EPA; interpolate ties by midrank.

    Percentile formula: 100 * (N - descending_midrank) / (N - 1).
    Consequently worst=0, best=100, all ties get the same percentile.
    """
    qualified = [r for r in records if r["usable_dropbacks"] >= minimum]
    if len(qualified) < 2:
        raise AssertionError(f"Not enough qualified QBs: n={len(qualified)}")
    n = len(qualified)
    epa_values = [float(r["qb_epa_per_dropback"]) for r in qualified]
    ranked: list[dict] = []
    for row in qualified:
        value = float(row["qb_epa_per_dropback"])
        better = sum(x > value for x in epa_values)
        equal = sum(x == value for x in epa_values)
        descending_midrank = better + (equal + 1) / 2
        percentile = 100 * (n - descending_midrank) / (n - 1)
        ranked.append({
            **row,
            "min_qualifying_dropbacks": minimum,
            "qualified_qb_count": n,
            "rank_descending": float(descending_midrank),
            "qualified_qb_percentile": float(percentile),
        })
    return sorted(ranked, key=lambda r: (r["rank_descending"], r["player_id"]))


def build_league_tables(seasons: list[int], cutoff, baselines: pl.DataFrame):
    all_rows: list[dict] = []
    qualified_rows: list[dict] = []
    sensitivity_rows: list[dict] = []
    audit_rows: list[dict] = []

    for season in seasons:
        baseline = baselines.filter(pl.col("season") == season).row(0, named=True)
        pbp, league_games = load_eligible_dropbacks(season, cutoff)
        verify_season_baseline(pbp, baseline, season)
        if league_games != int(baseline["league_games"]):
            raise AssertionError(f"{season}: league game count changed")
        if pbp.filter(pl.col("resolved_qb_id").is_null()).height:
            raise AssertionError(f"{season}: unresolved QB IDs")

        # Keep *all* QBs, including ineligible backups, for full reconciliation.
        grouped = pbp.group_by("resolved_qb_id").agg(
            pl.len().alias("eligible_dropbacks"),
            pl.col("valid_qb_epa").sum().alias("usable_dropbacks"),
            pl.col("qb_epa").sum().alias("qb_epa_sum"),
            (pl.col("qb_epa") > 0).sum().alias("positive_qb_epa_dropbacks"),
            pl.col("game_id").n_unique().alias("games_with_dropbacks"),
            pl.col("restored_scramble").sum().alias("restored_scramble_dropbacks"),
        ).rename({"resolved_qb_id": "player_id"})
        if grouped.height == 0:
            raise AssertionError(f"{season}: no QBs in the league grouping")
        if grouped.filter(pl.col("usable_dropbacks") <= 0).height:
            # A zero-usable player can exist in principle, but cannot have a mean.
            raise AssertionError(f"{season}: QB with no usable EPA dropbacks")
        grouped = grouped.with_columns(
            (pl.col("qb_epa_sum") / pl.col("usable_dropbacks")).alias("qb_epa_per_dropback"),
            (pl.col("positive_qb_epa_dropbacks") / pl.col("usable_dropbacks")).alias("qb_success_rate"),
            pl.lit(season).alias("season"),
            pl.lit(str(baseline["baseline_scope"])).alias("baseline_scope"),
        )
        if int(grouped["eligible_dropbacks"].sum()) != int(baseline["eligible_dropbacks"]):
            raise AssertionError(f"{season}: grouped eligible-dropback count mismatch")
        if int(grouped["usable_dropbacks"].sum()) != int(baseline["usable_dropbacks"]):
            raise AssertionError(f"{season}: grouped usable-dropback count mismatch")
        assert_close(
            float(grouped["qb_epa_sum"].sum()),
            float(baseline["league_qb_epa_sum"]),
            f"{season} full-league grouped QB EPA sum",
        )
        if grouped.select(pl.col("player_id").n_unique()).item() != grouped.height:
            raise AssertionError(f"{season}: duplicate QB IDs")

        records = grouped.to_dicts()
        primary_minimum = minimum_dropbacks(PRIMARY_MIN_DB, season, league_games)
        main_ranked = rankings_for_season(records, primary_minimum)
        qualified_rows.extend(main_ranked)
        all_rows.extend(records)
        for threshold in SENSITIVITY_MIN_DB:
            effective_minimum = minimum_dropbacks(threshold, season, league_games)
            for row in rankings_for_season(records, effective_minimum):
                sensitivity_rows.append({
                    "season": season,
                    "player_id": row["player_id"],
                    "threshold_full_season": threshold,
                    "threshold_effective": effective_minimum,
                    "qualified_qb_count": row["qualified_qb_count"],
                    "rank_descending": row["rank_descending"],
                    "qualified_qb_percentile": row["qualified_qb_percentile"],
                })

        audit_rows.append({
            "season": season,
            "baseline_scope": baseline["baseline_scope"],
            "cutoff_date": baseline["cutoff_date"],
            "league_games": league_games,
            "min_qualifying_dropbacks": primary_minimum,
            "distinct_qbs": grouped.height,
            "qualified_qbs": len(main_ranked),
            "total_eligible_dropbacks": int(grouped["eligible_dropbacks"].sum()),
            "total_usable_dropbacks": int(grouped["usable_dropbacks"].sum()),
            "league_usable_dropbacks": int(baseline["usable_dropbacks"]),
            "league_qb_epa_sum_reconstructed": float(grouped["qb_epa_sum"].sum()),
            "league_qb_epa_sum_expected": float(baseline["league_qb_epa_sum"]),
            "restored_scrambles": int(grouped["restored_scramble_dropbacks"].sum()),
            "missing_epa_dropbacks": int(grouped["eligible_dropbacks"].sum()) - int(grouped["usable_dropbacks"].sum()),
            "status": "PASS",
        })
        print(
            f"{season}: {grouped.height} QBs | "
            f"{len(main_ranked)} qualified (min {primary_minimum} DB) | "
            f"{int(grouped['usable_dropbacks'].sum()):,} usable dropbacks | PASS"
        )

    all_qbs = pl.DataFrame(all_rows).sort(["season", "player_id"])
    qualified_qbs = pl.DataFrame(qualified_rows).sort(["season", "rank_descending"])
    sensitivity = pl.DataFrame(sensitivity_rows).sort(["season", "threshold_full_season", "rank_descending"])
    audit = pl.DataFrame(audit_rows).sort("season")
    if audit.height != len(seasons):
        raise AssertionError("Missing year in qualification audit")
    if qualified_qbs.filter(
        (pl.col("qualified_qb_percentile") < 0) |
        (pl.col("qualified_qb_percentile") > 100)
    ).height:
        raise AssertionError("Qualified percentile outside [0, 100]")
    return all_qbs, qualified_qbs, sensitivity, audit


def build_study_qb_comparison(
    all_qbs: pl.DataFrame, qualified_qbs: pl.DataFrame, seasons: list[int]
) -> pl.DataFrame:
    if not STUDY_SEASON_PATH.is_file():
        raise FileNotFoundError(f"Missing study-season summary: {STUDY_SEASON_PATH}")
    study = pl.read_parquet(STUDY_SEASON_PATH)
    required = {"season", "player_id", "player_name", "starts", "usable_dropbacks", "qb_epa_sum"}
    if missing := required - set(study.columns):
        raise ValueError(f"Missing study-season fields: {sorted(missing)}")
    study = study.select(
        "season", pl.col("player_id").cast(pl.String), "player_name", "starts",
        pl.col("usable_dropbacks").alias("study_usable_dropbacks"),
        pl.col("qb_epa_sum").alias("study_qb_epa_sum"),
    )
    if study.height != len(seasons):
        raise AssertionError(f"Expected one study QB per year: {len(seasons)}; got {study.height}")
    if study.select(pl.struct("season", "player_id").n_unique()).item() != study.height:
        raise AssertionError("Duplicate study QB/season")

    full = all_qbs.select(
        "season", "player_id",
        pl.col("eligible_dropbacks").alias("fullseason_eligible_dropbacks"),
        pl.col("usable_dropbacks").alias("fullseason_usable_dropbacks"),
        pl.col("qb_epa_sum").alias("fullseason_qb_epa_sum"),
        pl.col("qb_epa_per_dropback").alias("fullseason_qb_epa_per_dropback"),
    )
    ranked = qualified_qbs.select(
        "season", "player_id", "min_qualifying_dropbacks", "qualified_qb_count",
        "rank_descending", "qualified_qb_percentile",
    )
    combined = (
        study.join(full, on=["season", "player_id"], how="left", validate="1:1")
        .join(ranked, on=["season", "player_id"], how="left", validate="1:1")
    )
    if combined.filter(pl.col("fullseason_usable_dropbacks").is_null()).height:
        raise AssertionError("Missing full-season QB records for study players")
    if combined.filter(pl.col("fullseason_usable_dropbacks") < pl.col("study_usable_dropbacks")).height:
        raise AssertionError("Study has more dropbacks than entire QB season")

    # The population must match *exactly* to call the ranking study-aligned.
    aligned_expr = (
        (pl.col("fullseason_usable_dropbacks") == pl.col("study_usable_dropbacks"))
        & ((pl.col("fullseason_qb_epa_sum") - pl.col("study_qb_epa_sum")).abs() <= 1e-6)
    )
    combined = combined.with_columns(
        aligned_expr.alias("fullseason_matches_study_starts"),
        pl.col("qualified_qb_percentile").is_not_null().alias("qualified"),
    ).with_columns(
        pl.when(pl.col("qualified") & pl.col("fullseason_matches_study_starts"))
        .then(pl.col("qualified_qb_percentile"))
        .otherwise(None)
        .alias("study_aligned_qualified_percentile"),
        pl.when(~pl.col("qualified"))
        .then(pl.lit("NOT_QUALIFIED"))
        .when(~pl.col("fullseason_matches_study_starts"))
        .then(pl.lit("FULL_SEASON_INCLUDES_NON_STUDY_PLAYS"))
        .otherwise(pl.lit("STUDY_ALIGNED"))
        .alias("interpretation_status"),
    ).sort(["player_name", "season"])
    return combined


def main() -> None:
    _study, seasons, cutoff = load_study()
    baselines = read_baselines(seasons, cutoff)
    all_qbs, qualified, sensitivity, audit = build_league_tables(seasons, cutoff, baselines)
    study_qbs = build_study_qb_comparison(all_qbs, qualified, seasons)
    if study_qbs.height != 20:
        raise AssertionError("Expected 20 study QB-season records")

    print("\n=== STUDY PLAYER SEASON PERCENTILES ===")
    for row in study_qbs.select(
        "season", "player_name", "study_usable_dropbacks", "fullseason_usable_dropbacks",
        "qualified_qb_percentile", "interpretation_status",
    ).iter_rows(named=True):
        pct = row["qualified_qb_percentile"]
        shown = f"{pct:.1f}" if pct is not None else "N/A"
        print(f"{row['season']}: {row['player_name']}: {shown} | "
              f"study DB {row['study_usable_dropbacks']}, full-season DB "
              f"{row['fullseason_usable_dropbacks']} | {row['interpretation_status']}")

    # Export only after league reconciliation, rank bounds, and scope checks.
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    all_qbs.write_parquet(ALL_PARQUET)
    all_qbs.write_csv(ALL_CSV)
    qualified.write_parquet(QUAL_PARQUET)
    qualified.write_csv(QUAL_CSV)
    study_qbs.write_parquet(STUDY_PARQUET)
    study_qbs.write_csv(STUDY_CSV)
    sensitivity.write_csv(SENSITIVITY_CSV)
    audit.write_csv(AUDIT_CSV)
    print("\nPASS: league QB EPA rankings generated and reconciled to 20 NFL baselines")
    print(f"Qualified leaderboard: {QUAL_PARQUET}")
    print(f"Study player comparison: {STUDY_CSV}")
    print(f"Audit: {AUDIT_CSV}")


if __name__ == "__main__":
    main()
