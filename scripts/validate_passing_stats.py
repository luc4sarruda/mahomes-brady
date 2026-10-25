"""Audit all 262 player-game passing rows against nflverse weekly player stats.

Run from the project root:
    python3 scripts/validate_passing_stats.py

This is a cross-pipeline consistency check, NOT independent verification:
both play-by-play and weekly statistics belong to the nflverse ecosystem.
Independent NFL/PFR box-score reviews must be performed separately.

Inputs:
    data/processed/qb_game_stats.parquet
    data/processed/qb_first_131_starts.parquet

Creates:
    data/raw/player_stats/stats_player_week_{season}.parquet (locally cached)
    reports/validation/passing_game_comparison.csv
    reports/validation/passing_discrepancies.csv
    reports/validation/official_boxscore_review_template.csv
    reports/validation/passing_validation_summary.md
"""

from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import random

import nflreadpy as nfl
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
STATS_PATH = ROOT / "data/processed/qb_game_stats.parquet"
MASTER_PATH = ROOT / "data/processed/qb_first_131_starts.parquet"
CACHE_DIR = ROOT / "data/raw/player_stats"
REPORT_DIR = ROOT / "reports/validation"

METRICS = ["attempts", "completions", "passing_yards", "passing_tds", "interceptions"]
REFERENCE_NAMES = {
    "attempts": "attempts",
    "completions": "completions",
    "passing_yards": "passing_yards",
    "passing_tds": "passing_tds",
    "passing_interceptions": "interceptions",
}
EDGE_GAME_IDS = ["2005_17_MIA_NE"]  # Known starter-attribution exception.
RANDOM_SEED = 131


def get_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"


def load_computed() -> tuple[pl.DataFrame, pl.DataFrame]:
    for path in [STATS_PATH, MASTER_PATH]:
        if not path.is_file():
            raise FileNotFoundError(f"Missing: {path}. Run the existing pipeline first.")

    computed = pl.read_parquet(STATS_PATH)
    master = pl.read_parquet(MASTER_PATH)

    required = {"player_id", "player_name", "game_id", "season", "week", "start_no", *METRICS}
    missing = required - set(computed.columns)
    if missing:
        raise ValueError(f"Missing computed columns: {sorted(missing)}")

    if computed.height != 262 or master.height != 262:
        raise AssertionError("Expected exactly 262 rows in both study tables")

    for table_name, table in [("computed", computed), ("master", master)]:
        if table.select(pl.struct("player_id", "game_id").n_unique()).item() != 262:
            raise AssertionError(f"Duplicate player-game pairs in {table_name}")

    for metric in METRICS:
        if computed.filter(pl.col(metric).is_null()).height:
            raise AssertionError(f"Missing computed values in {metric}")
    # Negative total passing yards are unusual but possible; do not prohibit
    # them as though they were counts. Only count metrics must be nonnegative.
    for metric in ["attempts", "completions", "passing_tds", "interceptions"]:
        if computed.filter(pl.col(metric) < 0).height:
            raise AssertionError(f"Negative count values in {metric}")
    if computed.filter(pl.col("completions") > pl.col("attempts")).height:
        raise AssertionError("Completions exceed attempts")
    if computed.filter(
        (pl.col("passing_tds") > pl.col("attempts"))
        | (pl.col("interceptions") > pl.col("attempts"))
    ).height:
        raise AssertionError("TD or INT count exceeds attempts")

    # Preserve the main table as our authoritative population; don't silently
    # drop a study game because it is absent from the weekly reference.
    computed_keys = computed.select("player_id", "game_id").sort("player_id", "game_id")
    master_keys = master.select("player_id", "game_id").sort("player_id", "game_id")
    if not computed_keys.equals(master_keys):
        raise AssertionError("Passing table does not cover exactly the 262 master starts")

    return computed.with_columns(pl.col("player_id").cast(pl.String)), master


def load_reference(seasons: list[int], selected_ids: list[str]) -> pl.DataFrame:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    batches = []
    needed = {"player_id", "game_id", "season_type", *REFERENCE_NAMES}

    for season in seasons:
        path = CACHE_DIR / f"stats_player_week_{season}.parquet"
        if path.exists():
            weekly = pl.read_parquet(path)
            print(f"{season}: loaded cached weekly player stats")
        else:
            print(f"{season}: downloading nflverse weekly player stats")
            weekly = nfl.load_player_stats(seasons=[season], summary_level="week")
            weekly.write_parquet(path)
            print(f"{season}: cached {weekly.height:,} weekly rows")

        missing = needed - set(weekly.columns)
        if missing:
            raise ValueError(f"{season} player stats missing fields: {sorted(missing)}")

        selected = (
            weekly.with_columns(pl.col("player_id").cast(pl.String))
            .filter((pl.col("season_type") == "REG") & pl.col("player_id").is_in(selected_ids))
            .select(["player_id", "game_id", *REFERENCE_NAMES])
            .rename({old: f"reference_{new}" for old, new in REFERENCE_NAMES.items()})
        )
        batches.append(selected)

    reference = pl.concat(batches, how="vertical_relaxed")
    if reference.select(pl.struct("player_id", "game_id").n_unique()).item() != reference.height:
        raise AssertionError("Duplicate player-game rows in weekly reference; inspect before proceeding")
    return reference


def compare(computed: pl.DataFrame, reference: pl.DataFrame) -> pl.DataFrame:
    table = computed.join(reference, on=["player_id", "game_id"], how="left")
    if table.height != 262:
        raise AssertionError("Comparison changed the number of study rows")

    table = table.with_columns([
        (pl.col(metric).cast(pl.Int64) - pl.col(f"reference_{metric}").cast(pl.Int64, strict=False))
        .alias(f"delta_{metric}") for metric in METRICS
    ])
    missing_ref = pl.any_horizontal([pl.col(f"reference_{m}").is_null() for m in METRICS])
    disagreement = pl.any_horizontal([pl.col(f"delta_{m}") != 0 for m in METRICS])
    return (
        table.with_columns(
            pl.when(missing_ref).then(pl.lit("MISSING_REFERENCE"))
            .when(disagreement).then(pl.lit("MISMATCH"))
            .otherwise(pl.lit("MATCH"))
            .alias("validation_status")
        ).sort("player_name", "start_no")
    )


def make_manual_review_template(compared: pl.DataFrame, master: pl.DataFrame) -> pl.DataFrame:
    # One random game in every player-season, plus known edge cases.
    # Independent checks must be verified manually against NFL/PFR box scores.
    rng = random.Random(RANDOM_SEED)
    selected_keys = set()
    for _, group in compared.group_by(["player_id", "season"]):
        chosen = rng.choice(group.get_column("game_id").to_list())
        selected_keys.add(chosen)
    selected_keys.update(EDGE_GAME_IDS)
    # Include observed 0-attempt games: high-impact silent-join failure signal.
    selected_keys.update(compared.filter(pl.col("attempts") == 0).get_column("game_id").to_list())

    rows = (
        compared.filter(pl.col("game_id").is_in(list(selected_keys)))
        .join(master.select("player_id", "game_id", "game_date", "opponent"),
              on=["player_id", "game_id"], how="left")
        .select("player_name", "season", "start_no", "game_id", "game_date", "opponent", *METRICS)
        .sort("player_name", "season", "start_no")
    )
    for field in ["official_source_url", "official_attempts", "official_completions",
                  "official_passing_yards", "official_passing_tds", "official_interceptions",
                  "reviewer", "verification_notes"]:
        rows = rows.with_columns(pl.lit(None, dtype=pl.String).alias(field))
    return rows


def write_reports(compared: pl.DataFrame, master: pl.DataFrame, seasons: list[int]):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    all_path = REPORT_DIR / "passing_game_comparison.csv"
    issues_path = REPORT_DIR / "passing_discrepancies.csv"
    manual_path = REPORT_DIR / "official_boxscore_review_template.csv"
    md_path = REPORT_DIR / "passing_validation_summary.md"

    compared.write_csv(all_path)
    problems = compared.filter(pl.col("validation_status") != "MATCH")
    problems.write_csv(issues_path)
    manual = make_manual_review_template(compared, master)
    manual.write_csv(manual_path)

    counts = {row["validation_status"]: row["len"] for row in
              compared.group_by("validation_status").agg(pl.len().alias("len")).to_dicts()}
    ok = counts.get("MATCH", 0)
    missing = counts.get("MISSING_REFERENCE", 0)
    mismatches = counts.get("MISMATCH", 0)
    checked_at = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Passing Statistics Validation Summary", "",
        f"- **Generated (UTC):** {checked_at}",
        f"- **Scope:** First 131 starts for each of two players; {compared.height} player-game rows",
        f"- **Seasons represented:** {', '.join(map(str, seasons))}",
        f"- **nflreadpy version:** {get_version('nflreadpy')}",
        f"- **Polars version:** {pl.__version__}",
        f"- **Rows matching nflverse weekly stats:** {ok}",
        f"- **Rows with mismatched stats:** {mismatches}",
        f"- **Rows with missing reference statistics:** {missing}",
        f"- **Planned independent NFL/PFR review rows:** {manual.height}", "",
        "## Interpretation", "",
        "These comparisons check agreement between a custom play-by-play aggregation and",
        "nflverse weekly player statistics, using player ID and game ID. **They are not",
        "independent verification of the underlying source**, because both products belong",
        "to the nflverse data ecosystem. A complete review requires an external NFL/PFR",
        "box-score sample, recorded in `official_boxscore_review_template.csv`.", "",
        "## Metric Definitions", "",
        "- Passing attempts: NFL-style official attempts, including spikes.",
        "- Completed passes: passes completed and credited to the QB.",
        "- Passing yards: passing yards credited to the QB.",
        "- Passing TDs: passing touchdowns credited to the QB.",
        "- Interceptions: passes intercepted while attributed to that QB.", "",
        "## Files", "",
        "- `passing_game_comparison.csv`: all player-game comparisons",
        "- `passing_discrepancies.csv`: only unmatched or differing rows",
        "- `official_boxscore_review_template.csv`: seeded, season-stratified external review", "",
        "## Validation State", "",
        "**INCOMPLETE** — External box-score review is pending."
        if not problems.height else "**BLOCKED** — Resolve weekly reference mismatches or missing records first.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return counts, manual.height


def main():
    computed, master = load_computed()
    seasons = sorted(computed["season"].unique().to_list())
    player_ids = computed["player_id"].unique().to_list()
    reference = load_reference(seasons, player_ids)
    compared = compare(computed, reference)
    counts, external_sample = write_reports(compared, master, seasons)

    print("\n=== WEEKLY REFERENCE AUDIT ===")
    print(f"Total rows: {compared.height}")
    print(f"Matches: {counts.get('MATCH', 0)}")
    print(f"Mismatches: {counts.get('MISMATCH', 0)}")
    print(f"Missing reference: {counts.get('MISSING_REFERENCE', 0)}")
    print(f"Independent NFL/PFR spot-check sample: {external_sample} games")
    print(f"Reports: {REPORT_DIR}")

    if counts.get("MISMATCH", 0) or counts.get("MISSING_REFERENCE", 0):
        raise SystemExit("AUDIT FAILED: inspect passing_discrepancies.csv before proceeding")
    print("CROSS-PIPELINE AUDIT PASSED; independent external box-score review is still required")


if __name__ == "__main__":
    main()
