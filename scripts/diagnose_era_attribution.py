"""Diagnose quarterback attribution and historical scramble coverage in NFL PBP.

Run from the repository root:
    python3 scripts/diagnose_era_attribution.py

The script is read-only with respect to raw/processed datasets. It writes
inspection reports under reports/validation/ and makes no automatic repairs.
"""

from pathlib import Path
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
PBP_DIR = ROOT / "data/raw/play_by_play"
STUDY = ROOT / "data/processed/qb_complete_stats.parquet"
OUTPUT = ROOT / "reports/validation"


def optional_col(name: str, available: set[str], dtype=pl.String):
    if name in available:
        expr = pl.col(name)
        return expr.cast(pl.String) if dtype == pl.String else expr
    return pl.lit(None, dtype=dtype)


def main() -> None:
    if not STUDY.is_file():
        raise FileNotFoundError(f"Missing study table: {STUDY}")

    study = pl.read_parquet(STUDY, columns=["season", "week", "game_id"])
    seasons = sorted(study["season"].unique().to_list())
    summary = []
    unresolved_rows = []
    missing_epa_rows = []
    historical_qb_run_rows = []

    for season in seasons:
        path = PBP_DIR / f"pbp_{season}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Missing source: {path}")

        lazy = pl.scan_parquet(path)
        columns = set(lazy.collect_schema().names())
        required = {
            "game_id", "play_id", "season_type", "week", "qb_dropback",
            "two_point_attempt", "qb_spike", "qb_kneel", "qb_scramble",
            "passer_player_id", "qb_epa", "play_type", "posteam",
        }
        if not required <= columns:
            raise ValueError(f"{season}: missing columns: {sorted(required - columns)}")

        lazy = lazy.filter(pl.col("season_type") == "REG")
        if season == 2026:
            last_week = int(study.filter(pl.col("season") == season)["week"].max())
            lazy = lazy.filter(pl.col("week") <= last_week)

        eligible = (
            (pl.col("qb_dropback").fill_null(0) == 1)
            & (pl.col("two_point_attempt").fill_null(0) == 0)
            & (pl.col("qb_spike").fill_null(0) == 0)
            & (pl.col("qb_kneel").fill_null(0) == 0)
        )
        scramble = pl.col("qb_scramble").fill_null(0) == 1
        passer_original = pl.col("passer_player_id").cast(pl.String)
        passer_alt = optional_col("passer_id", columns)
        rusher = optional_col("rusher_player_id", columns)
        resolved_id = pl.coalesce(
            passer_alt,
            passer_original,
            pl.when(scramble).then(rusher).otherwise(pl.lit(None, dtype=pl.String)),
        )
        valid_epa = pl.col("qb_epa").is_finite().fill_null(False)
        qb_run = (
            (pl.col("play_type") == "run")
            & (optional_col("rusher_player_position", columns) == "QB")
            & (pl.col("qb_kneel").fill_null(0) == 0)
        )

        metrics = lazy.select(
            eligible.sum().alias("eligible_dropbacks"),
            (eligible & passer_original.is_null()).sum().alias("missing_passer_player_id"),
            (eligible & passer_alt.is_null()).sum().alias("missing_passer_id"),
            (eligible & passer_original.is_null() & passer_alt.is_not_null()).sum()
            .alias("rescued_by_passer_id"),
            (eligible & resolved_id.is_null()).sum().alias("unresolved_after_fallback"),
            (eligible & scramble).sum().alias("eligible_scrambles"),
            qb_run.sum().alias("qb_position_runs"),
            (eligible & ~valid_epa).sum().alias("missing_qb_epa"),
            (eligible & scramble & passer_original.is_null()).sum()
            .alias("scrambles_missing_original_id"),
            (eligible & scramble & resolved_id.is_null()).sum()
            .alias("scrambles_unresolved"),
            (
                eligible & passer_alt.is_not_null() & passer_original.is_not_null()
                & (passer_alt != passer_original)
            ).sum().alias("passer_id_conflicts"),
        ).collect().row(0, named=True)
        summary.append({"season": season, "passer_id_available": "passer_id" in columns, **metrics})
        print(
            f"{season}: original missing={metrics['missing_passer_player_id']:,}; "
            f"rescued by passer_id={metrics['rescued_by_passer_id']:,}; "
            f"unresolved={metrics['unresolved_after_fallback']:,}; "
            f"scrambles={metrics['eligible_scrambles']:,}; "
            f"QB-position runs={metrics['qb_position_runs']:,}; "
            f"EPA missing={metrics['missing_qb_epa']}"
        )

        details = lazy.with_columns(
            resolved_id.alias("resolved_qb_id"),
            passer_alt.alias("passer_id_alt"),
            rusher.alias("rusher_id_source"),
        )
        detail_columns = [
            "game_id", "play_id", "week", "posteam", "play_type", "qb_dropback",
            "qb_scramble", "passer_player_id", "passer_id_alt", "rusher_id_source",
            "resolved_qb_id", "qb_epa",
        ]
        if "desc" in columns:
            detail_columns.append("desc")

        if metrics["unresolved_after_fallback"]:
            bad = details.filter(eligible & resolved_id.is_null()).select(detail_columns).collect()
            unresolved_rows.append(bad.with_columns(pl.lit(season).alias("season")))
        if metrics["missing_qb_epa"]:
            bad = details.filter(eligible & ~valid_epa).select(detail_columns).collect()
            missing_epa_rows.append(bad.with_columns(pl.lit(season).alias("season")))
        if season in {2003, 2004, 2005} and "rusher_player_position" in columns:
            historical_columns = ["game_id", "play_id", "week", "posteam", "play_type",
                                  "qb_scramble", "qb_dropback", "qb_kneel", "rusher_player_id"]
            if "desc" in columns:
                historical_columns.append("desc")
            runs = lazy.filter(qb_run).select(historical_columns).collect()
            historical_qb_run_rows.append(runs.with_columns(pl.lit(season).alias("season")))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(summary).sort("season").write_csv(OUTPUT / "era_attribution_diagnostics.csv")
    if unresolved_rows:
        pl.concat(unresolved_rows, how="diagonal_relaxed").write_csv(
            OUTPUT / "era_unresolved_dropbacks.csv"
        )
    if missing_epa_rows:
        pl.concat(missing_epa_rows, how="diagonal_relaxed").write_csv(
            OUTPUT / "era_missing_qb_epa_plays.csv"
        )
    if historical_qb_run_rows:
        pl.concat(historical_qb_run_rows, how="diagonal_relaxed").write_csv(
            OUTPUT / "era_2003_2005_qb_runs.csv"
        )
    print(f"\nDiagnostic reports saved to {OUTPUT}")
    print("IMPORTANT: Flagged historical QB runs are NOT automatically classified as scrambles.")
    print("No original PBP data or validated quarterback statistics have been modified.")


if __name__ == "__main__":
    main()
