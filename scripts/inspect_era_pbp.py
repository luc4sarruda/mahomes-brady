"""Audit league-wide play-by-play coverage before building era-adjusted baselines.

Run from the repository root:
    python3 scripts/inspect_era_pbp.py

This script inspects data quality and availability; it DOES NOT yet calculate
EPA baselines or change the validated 262-start quarterback dataset.

Output:
    reports/validation/era_pbp_source_audit.csv
"""

from pathlib import Path
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
STARTS_PATH = ROOT / "data/processed/qb_complete_stats.parquet"
PBP_DIR = ROOT / "data/raw/play_by_play"
REPORT_PATH = ROOT / "reports/validation/era_pbp_source_audit.csv"

REQUIRED_PBP_COLUMNS = {
    "game_id", "play_id", "season_type", "week", "qb_dropback",
    "qb_spike", "qb_kneel", "two_point_attempt", "qb_epa", "epa",
    "passer_player_id", "posteam", "qb_scramble", "sack",
}


def main() -> None:
    if not STARTS_PATH.is_file():
        raise FileNotFoundError(f"Integrated study table not found: {STARTS_PATH}")

    starts = pl.read_parquet(STARTS_PATH)
    needed = {"game_id", "season", "week", "player_id", "start_no"}
    absent = needed - set(starts.columns)
    if absent:
        raise ValueError(f"Study table missing columns: {sorted(absent)}")
    if starts.height != 262:
        raise AssertionError(f"Expected 262 starts, got {starts.height}")
    if starts.select(pl.struct("player_id", "game_id").n_unique()).item() != 262:
        raise AssertionError("Duplicate quarterback-game pairs in the study table")

    seasons = sorted(starts["season"].unique().to_list())
    results = []
    failures = []

    for season in seasons:
        pbp_path = PBP_DIR / f"pbp_{season}.parquet"
        if not pbp_path.is_file():
            raise FileNotFoundError(f"Missing league PBP source: {pbp_path}")

        lazy = pl.scan_parquet(pbp_path)
        missing_cols = REQUIRED_PBP_COLUMNS - set(lazy.collect_schema().names())
        if missing_cols:
            raise ValueError(f"{season}: missing PBP columns: {sorted(missing_cols)}")

        selected_games = set(
            starts.filter(pl.col("season") == season)["game_id"].to_list()
        )

        # Only the ongoing 2026 season gets a partial-season league benchmark.
        # We use the latest study week, not whatever later weeks a cached file
        # may contain. Dates and available games within that week remain an
        # explicit data-snapshot limitation to document in the analysis.
        pbp = lazy.filter(pl.col("season_type") == "REG")
        scope = "full_regular_season"
        cutoff_week = None
        if season == 2026:
            cutoff_week = int(
                starts.filter(pl.col("season") == season)["week"].max()
            )
            pbp = pbp.filter(pl.col("week") <= cutoff_week)
            scope = "through_study_week"

        dropback = pl.col("qb_dropback").fill_null(0) == 1
        eligible = (
            dropback
            & (pl.col("two_point_attempt").fill_null(0) == 0)
            & (pl.col("qb_spike").fill_null(0) == 0)
            & (pl.col("qb_kneel").fill_null(0) == 0)
        )
        attributed = eligible & pl.col("passer_player_id").is_not_null()
        usable = eligible & pl.col("qb_epa").is_finite().fill_null(False)
        identified_usable = (
            attributed & pl.col("qb_epa").is_finite().fill_null(False)
        )

        # Each count is computed over ALL NFL games of the season, not only
        # Brady/Mahomes games. This is essential for an unbiased league baseline.
        row = pbp.select(
            pl.len().alias("pbp_rows"),
            pl.col("game_id").n_unique().alias("league_games"),
            pl.col("game_id").filter(
                pl.col("game_id").is_in(list(selected_games))
            ).n_unique().alias("sample_games_found"),
            dropback.sum().alias("all_dropbacks"),
            eligible.sum().alias("eligible_dropbacks"),
            attributed.sum().alias("attributed_dropbacks"),
            usable.sum().alias("usable_qb_epa_dropbacks"),
            identified_usable.sum().alias("attributed_usable_dropbacks"),
            (eligible & (pl.col("qb_scramble").fill_null(0) == 1))
            .sum().alias("scramble_dropbacks"),
            (eligible & (pl.col("sack").fill_null(0) == 1))
            .sum().alias("sack_dropbacks"),
            pl.col("passer_player_id").filter(attributed)
            .n_unique().alias("distinct_passer_ids"),
        ).collect().row(0, named=True)

        eligible_n = int(row["eligible_dropbacks"])
        row["season"] = int(season)
        row["scope"] = scope
        row["through_week"] = cutoff_week
        row["sample_games_expected"] = len(selected_games)
        row["sample_games_missing"] = len(selected_games) - int(row["sample_games_found"])
        row["unattributed_dropbacks"] = eligible_n - int(row["attributed_dropbacks"])
        row["missing_qb_epa_dropbacks"] = eligible_n - int(row["usable_qb_epa_dropbacks"])
        row["qb_epa_coverage_pct"] = (
            100 * int(row["usable_qb_epa_dropbacks"]) / eligible_n
            if eligible_n else None
        )

        concerns = []
        if row["sample_games_missing"]:
            concerns.append("missing_study_games")
        if season != 2026 and row["league_games"] < 200:
            concerns.append("possible_subset_instead_of_full_league")
        if eligible_n == 0:
            concerns.append("no_eligible_dropbacks")
        if row["missing_qb_epa_dropbacks"]:
            concerns.append("missing_qb_epa_values")
        if row["unattributed_dropbacks"]:
            concerns.append("unattributed_dropbacks")
        row["status"] = "REVIEW" if concerns else "PASS"
        row["notes"] = ";".join(concerns)
        results.append(row)

        if row["sample_games_missing"] or (season != 2026 and row["league_games"] < 200):
            failures.append(f"{season}: {row['notes']}")

        print(
            f"{season}: {row['league_games']} league games | "
            f"{row['eligible_dropbacks']:,} eligible dropbacks | "
            f"QB EPA coverage {row['qb_epa_coverage_pct'] or 0:.2f}% | "
            f"study games {row['sample_games_found']}/{row['sample_games_expected']} | "
            f"{row['status']}"
        )

    report = pl.DataFrame(results).select(
        "season", "scope", "through_week", "status", "notes",
        "league_games", "sample_games_expected", "sample_games_found",
        "sample_games_missing", "pbp_rows", "all_dropbacks", "eligible_dropbacks",
        "attributed_dropbacks", "unattributed_dropbacks",
        "usable_qb_epa_dropbacks", "attributed_usable_dropbacks",
        "missing_qb_epa_dropbacks", "qb_epa_coverage_pct",
        "scramble_dropbacks", "sack_dropbacks", "distinct_passer_ids",
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report.write_csv(REPORT_PATH)
    print(f"\nSource coverage report: {REPORT_PATH}")

    if failures:
        raise AssertionError("League-wide PBP source validation failed: " + " | ".join(failures))

    print("Source scope validated. Review any missing EPA/player IDs before modeling.")


if __name__ == "__main__":
    main()
