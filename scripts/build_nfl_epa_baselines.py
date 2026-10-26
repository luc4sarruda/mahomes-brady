"""Build NFL regular-season quarterback EPA/dropback baselines by season.

Run from the repository root:
    python3 scripts/build_nfl_epa_baselines.py

Inputs:
    data/processed/qb_complete_stats.parquet
    data/raw/play_by_play/pbp_{season}.parquet

Outputs:
    data/processed/nfl_season_dropback_baselines.parquet
    data/processed/nfl_season_dropback_baselines.csv
    reports/validation/era_baseline_quality_audit.csv
    reports/validation/era_baseline_missing_epa_plays.csv (when relevant)

Method:
    A dropback is either an nflfastR qb_dropback, or a run with a
    qb_scramble tag. The second condition restores historical scrambles
    tagged after the dropback flag was computed. Every included play is
    counted once. Spike, kneel, and two-point plays are excluded.

    The league baseline weights plays, not quarterback-level averages.
    A single known 2019 missing-QB-EPA play is explicitly tolerated and
    excluded from the EPA numerator and denominator. All other missing
    EPA plays, unidentified QBs, or source integrity errors stop export.

    For the incomplete 2026 season, league data end on the last calendar
    date in the 131-start study, not merely on the last study week.

The script does not modify source play-by-play or existing QB statistics.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
STUDY_PATH = ROOT / "data/processed/qb_complete_stats.parquet"
PBP_DIR = ROOT / "data/raw/play_by_play"
OUTPUT_DIR = ROOT / "data/processed"
REPORT_DIR = ROOT / "reports/validation"

BASELINE_PARQUET = OUTPUT_DIR / "nfl_season_dropback_baselines.parquet"
BASELINE_CSV = OUTPUT_DIR / "nfl_season_dropback_baselines.csv"
AUDIT_CSV = REPORT_DIR / "era_baseline_quality_audit.csv"
MISSING_CSV = REPORT_DIR / "era_baseline_missing_epa_plays.csv"

# Investigated against the user's source data; do not generalize this exemption.
KNOWN_MISSING_EPA = {(2019, "2019_01_PIT_NE", 4166)}

REQUIRED_PBP = {
    "game_id", "play_id", "game_date", "season_type", "week",
    "play_type", "qb_dropback", "qb_scramble", "qb_kneel", "qb_spike",
    "two_point_attempt", "qb_epa", "passer_player_id", "rusher_player_id",
    "sack",
}


def game_count_expected(season: int) -> int | None:
    if season == 2001:
        return 248
    if season == 2022:
        return 271  # BUF-CIN was canceled and did not count.
    if 2021 <= season <= 2025:
        return 272
    if season < 2021:
        return 256
    return None  # The ongoing 2026 season is a partial sample.


def load_study() -> tuple[pl.DataFrame, list[int], date | None]:
    if not STUDY_PATH.is_file():
        raise FileNotFoundError(f"Missing study table: {STUDY_PATH}")
    study = pl.read_parquet(STUDY_PATH)
    required = {"season", "game_id", "game_date", "player_id", "start_no"}
    missing = required - set(study.columns)
    if missing:
        raise ValueError(f"Missing study fields: {sorted(missing)}")
    if study.height != 262:
        raise AssertionError(f"Expected 262 study starts, found {study.height}")
    if study.select(pl.struct("player_id", "game_id").n_unique()).item() != 262:
        raise AssertionError("Duplicate study player/game combinations")
    seasons = sorted(int(x) for x in study["season"].unique().to_list())
    cutoff = None
    if 2026 in seasons:
        last_date = study.filter(pl.col("season") == 2026).select(
            normalized_game_date().max()
        ).item()
        if last_date is None:
            raise AssertionError("Cannot determine final study date for 2026")
        cutoff = last_date
    return study, seasons, cutoff


def normalized_game_date() -> pl.Expr:
    """Parse ISO calendar dates from string, Date, or Datetime input.

    Polars 2.0 requires explicit string parsing instead of cast(Date).
    Keep only the calendar date for comparisons with the 2026 cutoff.
    """
    return (
        pl.col("game_date")
        .cast(pl.String)
        .str.slice(0, 10)
        .str.to_date(format="%Y-%m-%d", strict=True)
    )


def optional_id(column: str, available: set[str]) -> pl.Expr:
    return pl.col(column).cast(pl.String) if column in available else pl.lit(None, dtype=pl.String)


def load_eligible_dropbacks(season: int, cutoff: date | None) -> tuple[pl.DataFrame, int]:
    path = PBP_DIR / f"pbp_{season}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"Missing league PBP: {path}")
    lazy = pl.scan_parquet(path)
    available = set(lazy.collect_schema().names())
    absent = REQUIRED_PBP - available
    if absent:
        raise ValueError(f"{season}: missing required PBP columns: {sorted(absent)}")

    selected = sorted(REQUIRED_PBP | ({"passer_id", "posteam", "desc"} & available))
    lazy = (
        lazy.filter(pl.col("season_type") == "REG")
        .select(selected)
        .with_columns(normalized_game_date())
    )
    if season == 2026:
        if cutoff is None:
            raise AssertionError("2026 cutoff is required")
        lazy = lazy.filter(pl.col("game_date") <= pl.lit(cutoff))

    # These are separate expressions deliberately: source qb_dropback can lag
    # behind qb_scramble when historical charting flags were applied later.
    original = pl.col("qb_dropback").fill_null(0) == 1
    scramble_run = (
        (pl.col("play_type") == "run")
        & (pl.col("qb_scramble").fill_null(0) == 1)
    )
    permitted = (
        (pl.col("two_point_attempt").fill_null(0) == 0)
        & (pl.col("qb_spike").fill_null(0) == 0)
        & (pl.col("qb_kneel").fill_null(0) == 0)
    )
    # A play already tagged qb_dropback and scramble is included just once.
    lazy = lazy.with_columns(
        (original & permitted).alias("original_eligible_dropback"),
        (scramble_run & ~original & permitted).alias("restored_scramble"),
        ((original | scramble_run) & permitted).alias("corrected_eligible_dropback"),
    )
    data = lazy.collect()
    league_games = data["game_id"].n_unique()
    filtered = data.filter(pl.col("corrected_eligible_dropback"))
    # Resolved ID is needed for subsequent player-level analysis and serves
    # as an additional integrity check for this league-wide baseline.
    filtered = filtered.with_columns(
        pl.coalesce(
            optional_id("passer_id", available),
            pl.col("passer_player_id").cast(pl.String),
            pl.when(pl.col("qb_scramble").fill_null(0) == 1)
            .then(pl.col("rusher_player_id").cast(pl.String))
            .otherwise(pl.lit(None, dtype=pl.String)),
        ).alias("resolved_qb_id"),
        pl.col("qb_epa").is_finite().fill_null(False).alias("valid_qb_epa"),
    )
    return filtered, int(league_games)


def main() -> None:
    study, seasons, cutoff = load_study()
    baseline_rows = []
    audit_rows = []
    missing_rows = []
    failures = []

    for season in seasons:
        dropbacks, league_games = load_eligible_dropbacks(season, cutoff)
        expected_games = game_count_expected(season)
        study_games = set(study.filter(pl.col("season") == season)["game_id"].to_list())
        # Every game in the selected 131 starts must be covered by the
        # corrected regular-season PBP selection.
        present = set(dropbacks["game_id"].unique().to_list())
        missing_study_games = sorted(study_games - present)
        if missing_study_games:
            failures.append(f"{season}: study games missing dropbacks: {missing_study_games}")
        if expected_games is not None and league_games != expected_games:
            failures.append(
                f"{season}: expected {expected_games} league games; found {league_games}"
            )
        if dropbacks.height == 0:
            failures.append(f"{season}: no corrected dropbacks")
            continue

        unique_plays = int(dropbacks.select(pl.struct("game_id", "play_id").n_unique()).item())
        if unique_plays != dropbacks.height:
            failures.append(f"{season}: duplicate (game_id, play_id) in dropbacks")

        original_count = int(dropbacks["original_eligible_dropback"].sum())
        restored_count = int(dropbacks["restored_scramble"].sum())
        if original_count + restored_count != dropbacks.height:
            failures.append(f"{season}: corrected dropback partition failed")
        if season in (2001, 2002, 2003, 2004, 2005) and restored_count == 0:
            failures.append(f"{season}: expected to recover historical scramble dropbacks")

        unknown_id_count = dropbacks.filter(pl.col("resolved_qb_id").is_null()).height
        if unknown_id_count:
            failures.append(f"{season}: {unknown_id_count} corrected dropbacks without QB ID")

        missing_epa = dropbacks.filter(~pl.col("valid_qb_epa"))
        for record in missing_epa.select("game_id", "play_id").iter_rows(named=True):
            game, play = str(record["game_id"]), record["play_id"]
            key = (season, game, int(play)) if play is not None else None
            if key not in KNOWN_MISSING_EPA:
                failures.append(f"{season}: unexpected missing QB EPA on {game}, play {play}")
        if missing_epa.height:
            for record in missing_epa.select(
                "game_id", "play_id", "week", "play_type", "resolved_qb_id",
                "original_eligible_dropback", "restored_scramble",
            ).iter_rows(named=True):
                missing_rows.append({"season": season, **record})

        usable = dropbacks.filter(pl.col("valid_qb_epa"))
        if usable.height == 0:
            failures.append(f"{season}: no valid QB EPA values")
            continue
        n = int(usable.height)
        league_mean = float(usable["qb_epa"].mean())
        league_std = float(usable["qb_epa"].std()) if n > 1 else None
        league_sum = float(usable["qb_epa"].sum())
        success_rate = float((usable["qb_epa"] > 0).mean())
        scramble_count = dropbacks.filter(pl.col("qb_scramble").fill_null(0) == 1).height
        sacks = dropbacks.filter(pl.col("sack").fill_null(0) == 1).height
        scope = "through_study_date" if season == 2026 else "full_regular_season"

        baseline_rows.append({
            "season": season,
            "baseline_scope": scope,
            "cutoff_date": cutoff.isoformat() if season == 2026 else None,
            "league_games": league_games,
            "eligible_dropbacks": int(dropbacks.height),
            "usable_dropbacks": n,
            "league_qb_epa_sum": league_sum,
            "league_qb_epa_per_dropback": league_mean,
            "league_qb_epa_std": league_std,
            "league_qb_epa_success_rate": success_rate,
        })
        audit_rows.append({
            "season": season,
            "league_games": league_games,
            "study_games_expected": len(study_games),
            "study_games_found": len(study_games - set(missing_study_games)),
            "original_eligible_dropbacks": original_count,
            "restored_scramble_dropbacks": restored_count,
            "corrected_eligible_dropbacks": int(dropbacks.height),
            "scramble_dropbacks": scramble_count,
            "sack_dropbacks": sacks,
            "dropbacks_missing_qb_id": unknown_id_count,
            "dropbacks_missing_qb_epa": int(missing_epa.height),
            "usable_dropbacks": n,
            "qb_epa_coverage_pct": 100 * n / dropbacks.height,
        })
        print(
            f"{season}: {league_games} games | "
            f"{original_count:,} original + {restored_count:,} restored = "
            f"{dropbacks.height:,} dropbacks | "
            f"QB EPA {league_mean:+.4f}/DB | "
            f"missing EPA={missing_epa.height} | missing QB ID={unknown_id_count}"
        )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(audit_rows).sort("season").write_csv(AUDIT_CSV)
    if missing_rows:
        pl.DataFrame(missing_rows).sort(["season", "game_id", "play_id"]).write_csv(MISSING_CSV)
    elif MISSING_CSV.exists():
        MISSING_CSV.unlink()  # Avoid leaving a misleading stale prior report.

    if failures:
        raise AssertionError("Baseline validation failed:\n- " + "\n- ".join(failures))
    if len(baseline_rows) != len(seasons):
        raise AssertionError("Baseline season count does not match the study")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    baselines = pl.DataFrame(baseline_rows).sort("season")
    baselines.write_parquet(BASELINE_PARQUET)
    baselines.write_csv(BASELINE_CSV)
    print(f"\nPASS: {baselines.height} season baselines built")
    print(f"Baselines: {BASELINE_PARQUET}")
    print(f"Audit report: {AUDIT_CSV}")
    print("Next: attribute per-game QB EPA using the SAME corrected dropback definition.")


if __name__ == "__main__":
    main()
