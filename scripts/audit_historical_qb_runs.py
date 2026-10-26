"""Audit QB rushing plays potentially misclassified in historical NFL PBP.

Run from repository root:
    python3 scripts/audit_historical_qb_runs.py

Purpose:
    Identify running plays performed by players who are also credited with
    passing plays in the same regular season. This highlights potentially
    missing scramble tags in 2003-2005 without assuming every QB run was
    a scramble (some were designed runs or quarterback sneaks).

Input:
    data/raw/play_by_play/pbp_{season}.parquet (2001-2007)
    data/processed/qb_first_131_starts.parquet (optional, for study markers)

Outputs:
    reports/validation/historical_qb_runs_summary.csv
    reports/validation/historical_qb_run_candidates.csv

This script is READ-ONLY with respect to source and processed datasets.
"""

from pathlib import Path
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
PBP_DIR = ROOT / "data/raw/play_by_play"
MASTER_PATH = ROOT / "data/processed/qb_first_131_starts.parquet"
REPORT_DIR = ROOT / "reports/validation"
SEASONS = range(2001, 2008)

REQUIRED = {
    "game_id", "play_id", "season_type", "play_type",
    "rusher_player_id", "passer_player_id", "qb_scramble", "qb_dropback",
    "rush_attempt", "qb_kneel", "two_point_attempt",
}
OPTIONAL = {
    "passer_id", "posteam", "week", "rushing_yards", "desc",
    "pass_attempt", "sack", "rusher_player_name",
}


def read_season(season: int) -> pl.DataFrame:
    path = PBP_DIR / f"pbp_{season}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Source PBP not found: {path}")
    schema = set(pl.scan_parquet(path).collect_schema().names())
    missing = REQUIRED - schema
    if missing:
        raise ValueError(f"{season}: missing required PBP fields: {sorted(missing)}")
    selected = sorted(REQUIRED | (OPTIONAL & schema))
    df = (
        pl.scan_parquet(path)
        .filter(pl.col("season_type") == "REG")
        .select(selected)
        .collect()
    )
    defaults = {
        "passer_id": pl.String,
        "posteam": pl.String,
        "week": pl.Int64,
        "rushing_yards": pl.Float64,
        "desc": pl.String,
        "pass_attempt": pl.Float64,
        "sack": pl.Float64,
        "rusher_player_name": pl.String,
    }
    absent_exprs = [
        pl.lit(None, dtype=dtype).alias(name)
        for name, dtype in defaults.items()
        if name not in df.columns
    ]
    if absent_exprs:
        df = df.with_columns(absent_exprs)
    return df.with_columns(
        pl.col("rusher_player_id").cast(pl.String),
        pl.col("passer_player_id").cast(pl.String),
        pl.col("passer_id").cast(pl.String),
    )


def known_study_games() -> set[str]:
    if not MASTER_PATH.exists():
        print("Study master not found; proceeding without study-game markers.")
        return set()
    return set(pl.read_parquet(MASTER_PATH, columns=["game_id"])["game_id"].to_list())


def audit_one_season(df: pl.DataFrame, season: int, study_games: set[str]):
    # Identify plausible QBs from players who actually threw a pass or were
    # recorded as passers on a sack. A trick-play passer could also qualify;
    # this is a candidate search, not an authoritative QB-position roster.
    passing_play = (
        (pl.col("play_type") == "pass")
        | (pl.col("pass_attempt").fill_null(0) == 1)
        | (pl.col("sack").fill_null(0) == 1)
    )
    passing = df.filter(passing_play)
    passer_ids = set(passing["passer_player_id"].drop_nulls().to_list())
    passer_ids.update(passing["passer_id"].drop_nulls().to_list())
    if not passer_ids:
        raise AssertionError(f"{season}: no passing participants found")

    run = (
        (pl.col("play_type") == "run")
        & (pl.col("rush_attempt").fill_null(0) == 1)
        & (pl.col("qb_kneel").fill_null(0) == 0)
        & (pl.col("two_point_attempt").fill_null(0) == 0)
    )
    runs = df.filter(run & pl.col("rusher_player_id").is_in(sorted(passer_ids)))
    runs = runs.with_columns(
        pl.lit(season).alias("season"),
        (pl.col("qb_scramble").fill_null(0) == 1).alias("tagged_scramble"),
        (pl.col("qb_dropback").fill_null(0) == 1).alias("tagged_dropback"),
        pl.col("game_id").is_in(sorted(study_games)).alias("is_study_game"),
        (pl.col("rusher_player_id") == "00-0019596").alias("is_brady_run"),
    )

    n_scrambles_all = df.filter(
        (pl.col("qb_scramble").fill_null(0) == 1)
        & (pl.col("two_point_attempt").fill_null(0) == 0)
    ).height
    n_untagged = runs.filter(~pl.col("tagged_scramble")).height
    n_bad_dropback = runs.filter(pl.col("tagged_scramble") & ~pl.col("tagged_dropback")).height
    counts = {
        "season": season,
        "eligible_qb_like_passers": len(passer_ids),
        "league_scramble_tags": n_scrambles_all,
        "qb_run_candidates": runs.height,
        "qb_run_candidates_tagged_scramble": runs.filter(pl.col("tagged_scramble")).height,
        "qb_run_candidates_not_tagged_scramble": n_untagged,
        "qb_run_candidates_tagged_dropback": runs.filter(pl.col("tagged_dropback")).height,
        "tagged_scramble_missing_dropback_flag": n_bad_dropback,
        "brady_run_candidates": runs.filter(pl.col("is_brady_run")).height,
        "brady_run_candidates_tagged_scramble": runs.filter(
            pl.col("is_brady_run") & pl.col("tagged_scramble")
        ).height,
        "study_game_qb_run_candidates": runs.filter(pl.col("is_study_game")).height,
    }
    keep = [
        "season", "game_id", "play_id", "week", "posteam",
        "rusher_player_id", "rusher_player_name", "rushing_yards",
        "qb_dropback", "qb_scramble", "tagged_dropback", "tagged_scramble",
        "is_study_game", "is_brady_run", "desc",
    ]
    print(
        f"{season}: {runs.height} QB-run candidates; "
        f"{counts['qb_run_candidates_tagged_scramble']} tagged scrambles; "
        f"{n_untagged} untagged QB runs; "
        f"Brady runs={counts['brady_run_candidates']} "
        f"(scrambles={counts['brady_run_candidates_tagged_scramble']})"
    )
    return counts, runs.select(keep)


def main() -> None:
    study_games = known_study_games()
    summaries = []
    frames = []
    for season in SEASONS:
        data = read_season(season)
        summary, candidates = audit_one_season(data, season, study_games)
        summaries.append(summary)
        frames.append(candidates)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary_file = REPORT_DIR / "historical_qb_runs_summary.csv"
    plays_file = REPORT_DIR / "historical_qb_run_candidates.csv"
    pl.DataFrame(summaries).write_csv(summary_file)
    pl.concat(frames, how="vertical_relaxed").sort(
        ["season", "game_id", "play_id"]
    ).write_csv(plays_file)

    print(f"\nSummary: {summary_file}")
    print(f"Candidates: {plays_file}")
    print("WARNING: Non-tagged QB runs are NOT automatically scrambles.")
    print("No raw or processed football data were modified.")


if __name__ == "__main__":
    main()
