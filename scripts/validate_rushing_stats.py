"""Compare 262 QB rushing/sack game rows with nflverse weekly player stats.

Run after create_rushing_stats.py:
    python3 scripts/validate_rushing_stats.py

This is a cross-pipeline consistency audit, NOT independent validation.
Review a season-distributed sample of NFL/PFR box scores separately.
"""

from datetime import datetime, timezone
from pathlib import Path

import nflreadpy as nfl
import polars as pl


ROOT = Path(__file__).resolve().parents[1]
STATS_PATH = ROOT / "data/processed/qb_rushing_stats.parquet"
MASTER_PATH = ROOT / "data/processed/qb_first_131_starts.parquet"
CACHE_DIR = ROOT / "data/raw/player_stats"
REPORT_DIR = ROOT / "reports/validation"

# Local positive sack yardage is compared to the magnitude of the
# negative or positive reference field, accommodating version conventions.
REFERENCE_FIELDS = {
    "carries": "carries",
    "rushing_yards": "rushing_yards",
    "rushing_tds": "rushing_tds",
    "sacks_suffered": "sacks_taken",
    "sack_yards_lost": "sack_yards_lost",
}
METRICS = list(REFERENCE_FIELDS.values())


def load_inputs() -> tuple[pl.DataFrame, pl.DataFrame]:
    for path in (STATS_PATH, MASTER_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}; run the processing scripts first")
    stats = pl.read_parquet(STATS_PATH).with_columns(pl.col("player_id").cast(pl.String))
    master = pl.read_parquet(MASTER_PATH).with_columns(pl.col("player_id").cast(pl.String))
    if stats.height != 262 or master.height != 262:
        raise AssertionError("Expected exactly 262 rows in both tables")
    keys = ["player_id", "game_id"]
    for title, frame in (("rushing", stats), ("master", master)):
        if frame.select(pl.struct(*keys).n_unique()).item() != 262:
            raise AssertionError(f"Duplicate player-game keys in {title}")
    if not stats.select(keys).sort(keys).equals(master.select(keys).sort(keys)):
        raise AssertionError("Rushing table does not preserve the master population")
    missing = set(METRICS) - set(stats.columns)
    if missing:
        raise ValueError(f"Missing computed fields: {sorted(missing)}")
    return stats, master


def load_weekly(seasons: list[int], player_ids: list[str]) -> pl.DataFrame:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    batches = []
    required = {"player_id", "game_id", "season_type", *REFERENCE_FIELDS}
    for season in seasons:
        path = CACHE_DIR / f"stats_player_week_{season}.parquet"
        if path.exists():
            weekly = pl.read_parquet(path)
            print(f"{season}: using cached weekly stats")
        else:
            print(f"{season}: downloading weekly stats")
            weekly = nfl.load_player_stats(seasons=[season], summary_level="week")
            weekly.write_parquet(path)
        absent = required - set(weekly.columns)
        if absent:
            raise ValueError(f"Missing weekly stats fields for {season}: {sorted(absent)}")
        batch = (
            weekly.with_columns(pl.col("player_id").cast(pl.String))
            .filter((pl.col("season_type") == "REG") & pl.col("player_id").is_in(player_ids))
            .select(["player_id", "game_id", *REFERENCE_FIELDS])
            .rename({field: f"reference_{target}" for field, target in REFERENCE_FIELDS.items()})
        )
        batches.append(batch)
    reference = pl.concat(batches, how="vertical_relaxed")
    if reference.select(pl.struct("player_id", "game_id").n_unique()).item() != reference.height:
        raise AssertionError("Duplicate quarterback-game reference rows")
    return reference


def compare(stats: pl.DataFrame, reference: pl.DataFrame) -> pl.DataFrame:
    out = stats.join(reference, on=["player_id", "game_id"], how="left")
    if out.height != 262:
        raise AssertionError("Reference join changed sample size")
    # Convert reference sack yardage into a nonnegative loss magnitude.
    out = out.with_columns(
        pl.col("reference_sack_yards_lost").cast(pl.Int64, strict=False)
        .abs().alias("reference_sack_yards_lost")
    )
    out = out.with_columns([
        (pl.col(m).cast(pl.Int64) - pl.col(f"reference_{m}").cast(pl.Int64, strict=False))
        .alias(f"delta_{m}") for m in METRICS
    ])
    missing = pl.any_horizontal([pl.col(f"reference_{m}").is_null() for m in METRICS])
    mismatch = pl.any_horizontal([pl.col(f"delta_{m}") != 0 for m in METRICS])
    return (
        out.with_columns(
            pl.when(missing).then(pl.lit("MISSING_REFERENCE"))
            .when(mismatch).then(pl.lit("MISMATCH"))
            .otherwise(pl.lit("MATCH"))
            .alias("validation_status")
        )
        .sort(["player_name", "start_no"])
    )


def save_report(out: pl.DataFrame) -> dict[str, int]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_csv(REPORT_DIR / "rushing_game_comparison.csv")
    failures = out.filter(pl.col("validation_status") != "MATCH")
    failures.write_csv(REPORT_DIR / "rushing_discrepancies.csv")
    counts = {
        row["validation_status"]: row["len"]
        for row in out.group_by("validation_status").agg(pl.len().alias("len")).to_dicts()
    }
    lines = [
        "# Rushing, Mobility, and Sacks Validation", "",
        f"- Generated (UTC): {datetime.now(timezone.utc).isoformat()}",
        f"- QB-game rows: {out.height}",
        f"- Complete matches: {counts.get('MATCH', 0)}",
        f"- Mismatches: {counts.get('MISMATCH', 0)}",
        f"- Missing references: {counts.get('MISSING_REFERENCE', 0)}", "",
        "## Compared per game", "",
        "- Carries, rushing yards, rushing touchdowns", 
        "- Sacks suffered, magnitude of sack yardage lost", "",
        "## Methodological notes", "",
        "- Scrambles and designed runs are internal PBP-derived classifications;",
        "  weekly player statistics do not independently verify their splits.",
        "- The weekly and PBP sources both belong to nflverse. Matching them is",
        "  NOT independent NFL box-score verification.",
        "- Investigate any differences; do not change metrics just to pass validation.",
        "- Obtain a stratified external box-score sample before publication.", "",
        "## Status", "",
        "PASS (cross-pipeline only); independent sample pending." if not failures.height
        else "FAILED; review rushing_discrepancies.csv before proceeding.",
    ]
    (REPORT_DIR / "rushing_validation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main() -> None:
    stats, _ = load_inputs()
    seasons = sorted(stats["season"].unique().to_list())
    ids = stats["player_id"].unique().to_list()
    reference = load_weekly(seasons, ids)
    compared = compare(stats, reference)
    counts = save_report(compared)
    print("\n=== RUSHING AUDIT ===")
    print(f"Matches: {counts.get('MATCH', 0)}/262")
    print(f"Mismatches: {counts.get('MISMATCH', 0)}")
    print(f"Missing references: {counts.get('MISSING_REFERENCE', 0)}")
    print(f"Report directory: {REPORT_DIR}")
    if counts.get("MISMATCH", 0) or counts.get("MISSING_REFERENCE", 0):
        raise SystemExit("AUDIT FAILED; inspect rushing_discrepancies.csv")
    print("Cross-pipeline check passed. Independent box-score review is still required.")


if __name__ == "__main__":
    main()
