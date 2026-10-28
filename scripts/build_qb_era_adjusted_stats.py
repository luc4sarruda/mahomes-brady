"""Compute study-quarterback EPA and season-relative efficiency per start.

Usage (from repository root):
    python3 scripts/build_qb_era_adjusted_stats.py

Requires the validated league baselines and the exact, unchanged
``build_nfl_epa_baselines.py`` in the same scripts/ directory. We import its
PBP filtering/attribution function deliberately: league and player numerators
and denominators must use identical play eligibility criteria.

This program does not alter original PBP data, passing/rushing totals, or
league baselines. All project artifacts and descriptions are in English.
"""

from __future__ import annotations

import math
from pathlib import Path

import polars as pl

from build_nfl_epa_baselines import load_eligible_dropbacks, load_study

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports" / "validation"
BASELINES_PATH = PROCESSED / "nfl_season_dropback_baselines.parquet"

PLAYS_PATH = PROCESSED / "qb_era_dropback_plays.parquet"
GAME_PATH = PROCESSED / "qb_game_era_adjusted.parquet"
GAME_CSV = PROCESSED / "qb_game_era_adjusted.csv"
SEASON_PATH = PROCESSED / "qb_study_season_era_summary.parquet"
SEASON_CSV = PROCESSED / "qb_study_season_era_summary.csv"
CAREER_PATH = PROCESSED / "qb_first_131_era_summary.parquet"
CAREER_CSV = PROCESSED / "qb_first_131_era_summary.csv"
AUDIT_PATH = REPORTS / "qb_era_adjustment_quality_audit.csv"

STUDY_KEYS = ["player_id", "game_id"]
STUDY_REQUIRED = {
    "player_id", "player_name", "team", "game_id", "season", "week",
    "start_no", "game_date",
}
BASELINE_REQUIRED = {
    "season", "baseline_scope", "cutoff_date", "league_games",
    "eligible_dropbacks", "usable_dropbacks", "league_qb_epa_sum",
    "league_qb_epa_per_dropback", "league_qb_epa_success_rate",
}


def assert_close(observed: float, expected: float, label: str) -> None:
    if not math.isclose(float(observed), float(expected), rel_tol=1e-10, abs_tol=1e-7):
        raise AssertionError(f"{label}: observed={observed}, expected={expected}")


def read_baselines(seasons: list[int], cutoff) -> pl.DataFrame:
    if not BASELINES_PATH.is_file():
        raise FileNotFoundError(
            f"Missing league baselines: {BASELINES_PATH}\n"
            "Run python3 scripts/build_nfl_epa_baselines.py first."
        )
    baselines = pl.read_parquet(BASELINES_PATH)
    missing = BASELINE_REQUIRED - set(baselines.columns)
    if missing:
        raise ValueError(f"Baseline table missing columns: {sorted(missing)}")
    if baselines.height != len(seasons) or baselines["season"].n_unique() != len(seasons):
        raise AssertionError("Baseline must contain exactly one row per study season")
    if sorted(baselines["season"].to_list()) != seasons:
        raise AssertionError("Baseline seasons do not match the 262-start sample")
    for row in baselines.select("season", "baseline_scope", "cutoff_date").iter_rows(named=True):
        year = row["season"]
        expected_scope = "through_study_date" if year == 2026 else "full_regular_season"
        if row["baseline_scope"] != expected_scope:
            raise AssertionError(f"{year}: unexpected league baseline scope")
        if year == 2026 and str(row["cutoff_date"]) != cutoff.isoformat():
            raise AssertionError(
                f"2026 cutoff differs between study and baseline: "
                f"{row['cutoff_date']} versus {cutoff}"
            )
        if year != 2026 and row["cutoff_date"] is not None:
            raise AssertionError(f"{year}: full-season baseline has a cutoff date")
    return baselines


def verify_season_baseline(pbp: pl.DataFrame, baseline: dict, season: int) -> None:
    """Prove we are using exactly the same source population as the baseline."""
    valid = pbp.filter(pl.col("valid_qb_epa"))
    if pbp.height != int(baseline["eligible_dropbacks"]):
        raise AssertionError(f"{season}: source dropback count differs from validated baseline")
    if valid.height != int(baseline["usable_dropbacks"]):
        raise AssertionError(f"{season}: usable dropback count differs from baseline")
    assert_close(
        valid["qb_epa"].sum(), baseline["league_qb_epa_sum"],
        f"{season} league EPA sum",
    )
    assert_close(
        valid["qb_epa"].mean(), baseline["league_qb_epa_per_dropback"],
        f"{season} league EPA per dropback",
    )
    assert_close(
        (valid["qb_epa"] > 0).mean(), baseline["league_qb_epa_success_rate"],
        f"{season} league success rate",
    )
    if pbp.select(pl.struct("game_id", "play_id").n_unique()).item() != pbp.height:
        raise AssertionError(f"{season}: duplicate dropback game/play pairs")
    if pbp.filter(pl.col("resolved_qb_id").is_null()).height:
        raise AssertionError(f"{season}: a dropback lacks the resolved QB identifier")


def collect_sample_plays(
    study: pl.DataFrame, baselines: pl.DataFrame, seasons: list[int], cutoff
) -> tuple[pl.DataFrame, pl.DataFrame]:
    all_player_plays: list[pl.DataFrame] = []
    audit: list[dict] = []
    for season in seasons:
        season_study = study.filter(pl.col("season") == season)
        baseline = baselines.filter(pl.col("season") == season).row(0, named=True)
        pbp, league_games = load_eligible_dropbacks(season, cutoff)
        verify_season_baseline(pbp, baseline, season)
        if league_games != int(baseline["league_games"]):
            raise AssertionError(f"{season}: league game count changed")
        if "posteam" not in pbp.columns:
            raise ValueError(f"{season}: posteam required to check QB team attribution")

        game_ids = season_study["game_id"].to_list()
        games_with_any = set(
            pbp.filter(pl.col("game_id").is_in(game_ids))["game_id"].unique().to_list()
        )
        missing_games = sorted(set(game_ids) - games_with_any)
        if missing_games:
            raise AssertionError(f"{season}: missing study games in PBP: {missing_games}")

        # Join only on game_id first, then require the *actual* resolved player
        # identity and offensive team. This prevents attribution of a backup's
        # dropbacks to the starter (the 2005 Brady/Cassel case matters here).
        play_candidates = pbp.filter(pl.col("game_id").is_in(game_ids))
        qb_plays = (
            play_candidates.join(
                season_study.select("game_id", "player_id", "team"),
                on="game_id", how="inner", validate="m:1",
            )
            .filter(pl.col("resolved_qb_id") == pl.col("player_id"))
        )
        if qb_plays.height == 0:
            raise AssertionError(f"{season}: none of the study QB dropbacks were attributed")
        bad_team = qb_plays.filter(
            pl.col("posteam").is_null() | (pl.col("posteam") != pl.col("team"))
        )
        if bad_team.height:
            print("Unexpected QB/offense teams:")
            print(bad_team.select("game_id", "play_id", "player_id", "team", "posteam").head(8))
            raise AssertionError(f"{season}: QB dropbacks attributed to a different offense")

        identified_games = set(qb_plays["game_id"].unique().to_list())
        missing_qb_games = sorted(set(game_ids) - identified_games)
        if missing_qb_games:
            raise AssertionError(f"{season}: no attributed study QB dropbacks: {missing_qb_games}")
        unusable = qb_plays.filter(~pl.col("valid_qb_epa"))
        if unusable.height:
            print("Study quarterback plays without valid QB EPA:")
            print(unusable.select("game_id", "play_id", "player_id", "qb_epa"))
            raise AssertionError(f"{season}: expected finite EPA on every study QB dropback")

        # Use only the columns necessary for reproducibility/inspection.
        out = qb_plays.select(
            pl.lit(season).alias("season"),
            "game_id", "play_id", "player_id", "posteam", "resolved_qb_id",
            "qb_epa", "valid_qb_epa", "qb_dropback", "qb_scramble",
            "sack", "original_eligible_dropback", "restored_scramble",
        )
        all_player_plays.append(out)
        restored = int(qb_plays["restored_scramble"].sum())
        audit.append({
            "season": season,
            "baseline_scope": baseline["baseline_scope"],
            "league_eligible_dropbacks": pbp.height,
            "study_games": season_study.height,
            "study_qb_games_found": len(identified_games),
            "study_qb_eligible_dropbacks": qb_plays.height,
            "study_qb_usable_dropbacks": qb_plays.height - unusable.height,
            "study_qb_restored_scrambles": restored,
            "study_qb_missing_epa": unusable.height,
            "study_qb_team_mismatches": bad_team.height,
        })
        print(
            f"{season}: {season_study.height} starts | "
            f"{qb_plays.height:,} QB dropbacks | "
            f"{restored} historical scrambles restored | "
            f"{unusable.height} missing QB EPA"
        )
    return pl.concat(all_player_plays, how="vertical"), pl.DataFrame(audit).sort("season")


def add_rates(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        (pl.col("qb_epa_sum") / pl.col("usable_dropbacks")).alias("qb_epa_per_dropback"),
        (pl.col("positive_qb_epa_dropbacks") / pl.col("usable_dropbacks")).alias("qb_epa_success_rate"),
        (pl.col("baseline_expected_epa") / pl.col("usable_dropbacks")).alias("expected_league_epa_per_dropback"),
        (pl.col("relative_qb_epa_total") / pl.col("usable_dropbacks")).alias("relative_qb_epa_per_dropback"),
    ).with_columns(
        (100 * (pl.col("qb_epa_success_rate") - pl.col("baseline_expected_success") / pl.col("usable_dropbacks"))).alias(
            "relative_qb_epa_success_rate_pp"
        )
    )


def build_game_table(study: pl.DataFrame, plays: pl.DataFrame, baselines: pl.DataFrame) -> pl.DataFrame:
    grouped = plays.group_by("player_id", "game_id").agg(
        pl.len().alias("eligible_dropbacks"),
        pl.col("valid_qb_epa").sum().alias("usable_dropbacks"),
        pl.col("qb_epa").sum().alias("qb_epa_sum"),
        (pl.col("qb_epa") > 0).sum().alias("positive_qb_epa_dropbacks"),
        (pl.col("qb_scramble").fill_null(0) == 1).sum().alias("scramble_dropbacks"),
        (pl.col("sack").fill_null(0) == 1).sum().alias("sack_dropbacks"),
        pl.col("restored_scramble").sum().alias("restored_scramble_dropbacks"),
    )
    if grouped.select(pl.struct("player_id", "game_id").n_unique()).item() != grouped.height:
        raise AssertionError("Duplicate QB game keys in aggregated EPA")
    games = study.join(grouped, on=STUDY_KEYS, how="left", validate="1:1")
    if games.height != 262:
        raise AssertionError(f"Expected 262 QB games, got {games.height}")
    if games.filter(pl.col("eligible_dropbacks").is_null()).height:
        print(games.filter(pl.col("eligible_dropbacks").is_null()).select("player_name", "game_id"))
        raise AssertionError("Some study games have no attributed QB dropbacks")
    if games.filter((pl.col("usable_dropbacks") != pl.col("eligible_dropbacks")) | (pl.col("usable_dropbacks") <= 0)).height:
        raise AssertionError("Study QB dropbacks have missing EPA or zero eligible plays")

    baseline_cols = baselines.select(
        "season", "baseline_scope", "cutoff_date",
        pl.col("league_qb_epa_per_dropback"),
        pl.col("league_qb_epa_success_rate"),
        pl.col("usable_dropbacks").alias("league_usable_dropbacks"),
    )
    games = games.join(baseline_cols, on="season", how="left", validate="m:1")
    if games.filter(pl.col("league_qb_epa_per_dropback").is_null()).height:
        raise AssertionError("Some QB games have no matching league baseline")
    games = games.with_columns(
        (pl.col("qb_epa_sum") / pl.col("usable_dropbacks")).alias("qb_epa_per_dropback"),
        (pl.col("positive_qb_epa_dropbacks") / pl.col("usable_dropbacks")).alias("qb_epa_success_rate"),
    ).with_columns(
        (pl.col("qb_epa_per_dropback") - pl.col("league_qb_epa_per_dropback")).alias("relative_qb_epa_per_dropback"),
        (pl.col("qb_epa_sum") - pl.col("usable_dropbacks") * pl.col("league_qb_epa_per_dropback")).alias("relative_qb_epa_total"),
        (100 * (pl.col("qb_epa_success_rate") - pl.col("league_qb_epa_success_rate"))).alias("relative_qb_epa_success_rate_pp"),
    ).sort("player_name", "start_no")
    return games


def aggregate_study_games(games: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    grouped = games.group_by(keys).agg(
        pl.len().alias("starts"),
        pl.col("eligible_dropbacks").sum(),
        pl.col("usable_dropbacks").sum(),
        pl.col("qb_epa_sum").sum(),
        pl.col("positive_qb_epa_dropbacks").sum(),
        pl.col("scramble_dropbacks").sum(),
        pl.col("sack_dropbacks").sum(),
        pl.col("restored_scramble_dropbacks").sum(),
        pl.col("relative_qb_epa_total").sum(),
        (pl.col("usable_dropbacks") * pl.col("league_qb_epa_per_dropback")).sum().alias("baseline_expected_epa"),
        (pl.col("usable_dropbacks") * pl.col("league_qb_epa_success_rate")).sum().alias("baseline_expected_success"),
    )
    if grouped.filter(pl.col("usable_dropbacks") <= 0).height:
        raise AssertionError("Invalid zero-dropback aggregated study group")
    grouped = add_rates(grouped)
    check = grouped.filter(
        (pl.col("qb_epa_sum") - pl.col("baseline_expected_epa") - pl.col("relative_qb_epa_total")).abs() > 1e-7
    )
    if check.height:
        raise AssertionError("Relative EPA aggregation consistency check failed")
    return grouped.sort(keys)


def main() -> None:
    study, seasons, cutoff = load_study()
    missing = STUDY_REQUIRED - set(study.columns)
    if missing:
        raise ValueError(f"Study table missing columns: {sorted(missing)}")
    study = study.with_columns(pl.col("player_id").cast(pl.String))
    baselines = read_baselines(seasons, cutoff)
    plays, audit = collect_sample_plays(study, baselines, seasons, cutoff)

    games = build_game_table(study, plays, baselines)
    season_summary = aggregate_study_games(games, ["player_id", "player_name", "season"])
    career_summary = aggregate_study_games(games, ["player_id", "player_name"])
    if career_summary.height != 2 or season_summary.height != len(seasons):
        raise AssertionError("Unexpected player/season group count")
    for row in career_summary.iter_rows(named=True):
        if int(row["starts"]) != 131:
            raise AssertionError(f"{row['player_name']} does not have 131 starts")
        print(
            f"{row['player_name']}: {row['starts']} starts | "
            f"{row['usable_dropbacks']:,} dropbacks | "
            f"QB EPA/DB {row['qb_epa_per_dropback']:+.4f} | "
            f"relative EPA/DB {row['relative_qb_epa_per_dropback']:+.4f}"
        )
    if sum(audit["study_qb_eligible_dropbacks"]) != plays.height:
        raise AssertionError("Audit does not reconcile to player play count")
    if int(games["usable_dropbacks"].sum()) != plays.height:
        raise AssertionError("Game totals do not reconcile to study play count")

    # Write datasets only after every validation and cross-check succeeds.
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    plays.sort("season", "game_id", "play_id", "player_id").write_parquet(PLAYS_PATH)
    games.write_parquet(GAME_PATH)
    games.write_csv(GAME_CSV)
    season_summary.write_parquet(SEASON_PATH)
    season_summary.write_csv(SEASON_CSV)
    career_summary.write_parquet(CAREER_PATH)
    career_summary.write_csv(CAREER_CSV)
    audit.write_csv(AUDIT_PATH)
    print(f"\nPASS: {games.height} QB games / {career_summary.height} players")
    print(f"Game-level analysis: {GAME_PATH}")
    print(f"Player summaries: {CAREER_CSV}")
    print(f"Validation report: {AUDIT_PATH}")
    print("Next: interpret the study findings in 03_era_adjusted_analysis.ipynb")


if __name__ == "__main__":
    main()
