"""Build centered three-season NFL EPA baselines and study QB comparisons.

Run from the project root:
    python3 scripts/build_three_year_relative_epa.py

This pipeline consumes the previously validated league-season and study-game
aggregates. It does not reread or modify play-by-play data.

Window policy:
- Separate historical eras: a window may never cross a missing-year gap.
- For full seasons, use the preceding/current/following full seasons when
  all are available; use two adjacent full seasons at era boundaries.
- Never use a partial future season to redefine a full-season reference.
- For the final partial study season (2026), use the two preceding full
  seasons plus the partial current season, and flag the window provisional.

All league means are weighted by valid NFL dropbacks. The study QB's game,
season, and 131-start comparisons are weighted by THEIR valid dropbacks.
"""

from __future__ import annotations

import math
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
AUDIT_DIR = ROOT / "reports" / "validation"

LEAGUE_INPUT = PROCESSED / "nfl_season_dropback_baselines.parquet"
GAMES_INPUT = PROCESSED / "qb_game_era_adjusted.parquet"
SEASON_INPUT = PROCESSED / "qb_study_season_era_summary.parquet"
CAREER_INPUT = PROCESSED / "qb_first_131_era_summary.parquet"

LEAGUE_OUTPUT = PROCESSED / "nfl_three_year_dropback_baselines.parquet"
GAMES_OUTPUT = PROCESSED / "qb_game_three_year_relative.parquet"
SEASON_OUTPUT = PROCESSED / "qb_study_season_three_year_summary.parquet"
CAREER_OUTPUT = PROCESSED / "qb_first_131_three_year_summary.parquet"
AUDIT_OUTPUT = AUDIT_DIR / "three_year_relative_quality_audit.csv"

LEAGUE_REQUIRED = {
    "season", "baseline_scope", "cutoff_date", "usable_dropbacks",
    "league_qb_epa_sum", "league_qb_epa_per_dropback",
}
GAME_REQUIRED = {
    "player_id", "player_name", "game_id", "season", "start_no",
    "usable_dropbacks", "qb_epa_sum", "qb_epa_per_dropback",
    "relative_qb_epa_total", "relative_qb_epa_per_dropback",
    "league_qb_epa_per_dropback",
}


def close(a: float, b: float, label: str, tol: float = 1e-8) -> None:
    if not math.isclose(float(a), float(b), abs_tol=tol, rel_tol=1e-10):
        raise AssertionError(f"{label}: {a!r} != {b!r}")


def read_and_validate_inputs() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    files = [LEAGUE_INPUT, GAMES_INPUT, SEASON_INPUT, CAREER_INPUT]
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        raise FileNotFoundError("Missing validated prerequisites:\n" + "\n".join(missing))
    league, games, seasons, career = [pl.read_parquet(p) for p in files]
    for df, needed, name in ((league, LEAGUE_REQUIRED, "league"), (games, GAME_REQUIRED, "games")):
        absent = needed - set(df.columns)
        if absent:
            raise ValueError(f"{name}: missing columns: {sorted(absent)}")
    if league.height != 20 or league["season"].n_unique() != 20:
        raise AssertionError("Expected exactly 20 distinct league season baselines")
    if games.height != 262 or games.select(pl.struct("player_id", "game_id").n_unique()).item() != 262:
        raise AssertionError("Expected 262 distinct study player/game rows")
    if seasons.height != 20 or career.height != 2:
        raise AssertionError("Expected 20 study player-seasons and two QB career rows")
    if set(games["season"].unique().to_list()) != set(league["season"].to_list()):
        raise AssertionError("Study seasons and league baseline seasons differ")
    if games.filter(pl.col("usable_dropbacks").is_null() | (pl.col("usable_dropbacks") <= 0)).height:
        raise AssertionError("Study game with missing or nonpositive dropback count")
    if league.filter(pl.col("usable_dropbacks").is_null() | (pl.col("usable_dropbacks") <= 0)).height:
        raise AssertionError("League season with missing or nonpositive dropback count")
    if league.filter(pl.col("league_qb_epa_sum").is_null() | pl.col("league_qb_epa_per_dropback").is_null()).height:
        raise AssertionError("Missing league EPA numerator or rate")
    if games.filter(pl.col("qb_epa_sum").is_null() | pl.col("qb_epa_per_dropback").is_null()).height:
        raise AssertionError("Missing QB EPA numerator or rate")

    for row in league.iter_rows(named=True):
        close(row["league_qb_epa_sum"] / row["usable_dropbacks"], row["league_qb_epa_per_dropback"], f"{row['season']} league rate")
    for row in games.iter_rows(named=True):
        close(row["qb_epa_sum"] / row["usable_dropbacks"], row["qb_epa_per_dropback"], f"{row['game_id']} player rate")
        close(row["qb_epa_per_dropback"] - row["league_qb_epa_per_dropback"], row["relative_qb_epa_per_dropback"], f"{row['game_id']} annual relative rate")
    for row in career.iter_rows(named=True):
        player = games.filter(pl.col("player_id") == row["player_id"]).sort("start_no")
        if player.height != 131 or player["start_no"].to_list() != list(range(1, 132)):
            raise AssertionError(f"Missing or duplicate career start for {row['player_name']}")
        close(player["qb_epa_sum"].sum(), row["qb_epa_sum"], f"{row['player_name']} career sum")
        if int(player["usable_dropbacks"].sum()) != int(row["usable_dropbacks"]):
            raise AssertionError(f"{row['player_name']}: career dropback reconciliation failed")
    # The only partial season in this particular research snapshot must be the most recent one.
    partial_years = league.filter(pl.col("baseline_scope") != "full_regular_season")["season"].to_list()
    if partial_years != [max(league["season"].to_list())]:
        raise AssertionError(f"Expected one last partial season, found {partial_years}")
    partial = league.filter(pl.col("season") == partial_years[0]).row(0, named=True)
    if partial["baseline_scope"] != "through_study_date" or partial["cutoff_date"] is None:
        raise AssertionError("Final partial baseline must carry the validated study-date cutoff")
    return league.sort("season"), games, seasons, career


def contiguous_eras(years: list[int]) -> list[list[int]]:
    eras: list[list[int]] = []
    for year in sorted(years):
        if not eras or year != eras[-1][-1] + 1:
            eras.append([year])
        else:
            eras[-1].append(year)
    return eras


def window_for_season(target: int, era: list[int], scopes: dict[int, str]) -> tuple[list[int], str, bool]:
    """Choose windows without bridging eras or blending partial data into full years."""
    full = [s for s in era if scopes[s] == "full_regular_season"]
    partial = [s for s in era if scopes[s] != "full_regular_season"]
    if len(full) < 2 or len(partial) > 1:
        raise AssertionError("Each study era needs >=2 full seasons and <=1 partial final season")
    if partial and partial[0] != era[-1]:
        raise AssertionError("Partial season must be the last season of its era")
    if target in full:
        idx = full.index(target)
        window = full[max(0, idx - 1): min(len(full), idx + 2)]
        kind = "centered_3_full_seasons" if len(window) == 3 else "edge_2_full_seasons"
        return window, kind, False
    if partial == [target]:
        return full[-2:] + [target], "trailing_2_full_plus_partial", True
    raise AssertionError(f"Season {target} is not in its assigned era")


def build_window_baselines(league: pl.DataFrame) -> pl.DataFrame:
    eras = contiguous_eras([int(s) for s in league["season"].to_list()])
    if len(eras) != 2 or len(eras[0]) != 10 or len(eras[1]) != 10:
        raise AssertionError(f"Unexpected study eras: {eras}")
    scopes = {int(r["season"]): r["baseline_scope"] for r in league.iter_rows(named=True)}
    by_year = {int(r["season"]): r for r in league.iter_rows(named=True)}
    rows: list[dict] = []
    for era in eras:
        for target in era:
            window, kind, provisional = window_for_season(target, era, scopes)
            total_epa = sum(float(by_year[year]["league_qb_epa_sum"]) for year in window)
            total_db = sum(int(by_year[year]["usable_dropbacks"]) for year in window)
            if total_db <= 0 or not math.isfinite(total_epa / total_db):
                raise AssertionError(f"{target}: invalid three-year baseline")
            mean = total_epa / total_db
            rows.append({
                "season": target,
                "window_seasons": ",".join(map(str, window)),
                "window_kind": kind,
                "provisional_partial_window": provisional,
                "window_season_count": len(window),
                "window_league_usable_dropbacks": total_db,
                "window_league_qb_epa_sum": total_epa,
                "three_year_league_qb_epa_per_dropback": mean,
                "annual_league_qb_epa_per_dropback": float(by_year[target]["league_qb_epa_per_dropback"]),
                "annual_baseline_scope": scopes[target],
                "annual_cutoff_date": str(by_year[target]["cutoff_date"]) if by_year[target]["cutoff_date"] is not None else None,
            })
            print(f"{target}: [{', '.join(map(str, window))}] {kind} | {total_db:,} league DB | 3-year baseline {mean:+.4f}")
    out = pl.DataFrame(rows).sort("season")
    if out.height != league.height or out["season"].n_unique() != league.height:
        raise AssertionError("Window baselines do not cover every study season")
    # Key methodological guardrails, independent of the numeric calculations.
    if out.filter((pl.col("season") == 2010) & (pl.col("window_seasons").str.contains("2017"))).height:
        raise AssertionError("Historical study eras were accidentally bridged")
    if "2026" in str(out.filter(pl.col("season") == 2025)["window_seasons"].item()):
        raise AssertionError("2025 full-season reference must not incorporate partial 2026")
    return out


def attach_and_validate_games(games: pl.DataFrame, windows: pl.DataFrame) -> pl.DataFrame:
    joined = games.join(
        windows.select(
            "season", "window_seasons", "window_kind", "provisional_partial_window",
            "window_league_usable_dropbacks", "three_year_league_qb_epa_per_dropback",
        ),
        on="season", how="left", validate="m:1",
    )
    if joined.height != 262 or joined.filter(pl.col("three_year_league_qb_epa_per_dropback").is_null()).height:
        raise AssertionError("Not all 262 games received a valid three-year NFL baseline")
    joined = joined.with_columns(
        (pl.col("qb_epa_sum") - pl.col("usable_dropbacks") * pl.col("three_year_league_qb_epa_per_dropback")).alias("three_year_relative_qb_epa_total"),
        (pl.col("qb_epa_per_dropback") - pl.col("three_year_league_qb_epa_per_dropback")).alias("three_year_relative_qb_epa_per_dropback"),
    ).with_columns(
        (pl.col("three_year_relative_qb_epa_per_dropback") - pl.col("relative_qb_epa_per_dropback")).alias("three_year_minus_annual_relative_epa_per_dropback")
    )
    for row in joined.iter_rows(named=True):
        close(
            row["three_year_relative_qb_epa_total"] / row["usable_dropbacks"],
            row["three_year_relative_qb_epa_per_dropback"],
            f"{row['game_id']} three-year relative rate",
        )
    return joined.sort("player_name", "start_no")


def aggregate_games(games: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    out = games.group_by(by).agg(
        pl.len().alias("starts"),
        pl.col("usable_dropbacks").sum(),
        pl.col("qb_epa_sum").sum(),
        pl.col("relative_qb_epa_total").sum(),
        pl.col("three_year_relative_qb_epa_total").sum(),
        (pl.col("usable_dropbacks") * pl.col("league_qb_epa_per_dropback")).sum().alias("annual_baseline_expected_epa"),
        (pl.col("usable_dropbacks") * pl.col("three_year_league_qb_epa_per_dropback")).sum().alias("three_year_baseline_expected_epa"),
    ).with_columns(
        (pl.col("qb_epa_sum") / pl.col("usable_dropbacks")).alias("qb_epa_per_dropback"),
        (pl.col("relative_qb_epa_total") / pl.col("usable_dropbacks")).alias("annual_relative_qb_epa_per_dropback"),
        (pl.col("three_year_relative_qb_epa_total") / pl.col("usable_dropbacks")).alias("three_year_relative_qb_epa_per_dropback"),
        (pl.col("annual_baseline_expected_epa") / pl.col("usable_dropbacks")).alias("annual_expected_league_epa_per_dropback"),
        (pl.col("three_year_baseline_expected_epa") / pl.col("usable_dropbacks")).alias("three_year_expected_league_epa_per_dropback"),
    ).with_columns(
        (pl.col("three_year_relative_qb_epa_per_dropback") - pl.col("annual_relative_qb_epa_per_dropback")).alias("three_year_minus_annual_relative_epa_per_dropback"),
    )
    for r in out.iter_rows(named=True):
        close(r["qb_epa_sum"] - r["three_year_baseline_expected_epa"], r["three_year_relative_qb_epa_total"], "aggregated three-year EPA reconciliation")
        close(r["qb_epa_sum"] - r["annual_baseline_expected_epa"], r["relative_qb_epa_total"], "aggregated annual EPA reconciliation")
    return out.sort(by)


def main() -> None:
    league, games, original_seasons, original_career = read_and_validate_inputs()
    windows = build_window_baselines(league)
    enriched = attach_and_validate_games(games, windows)
    by_season = aggregate_games(enriched, ["player_id", "player_name", "season"])
    career = aggregate_games(enriched, ["player_id", "player_name"])
    if by_season.height != 20 or career.height != 2:
        raise AssertionError("Unexpected number of aggregated study QB rows")
    for row in career.iter_rows(named=True):
        if row["starts"] != 131:
            raise AssertionError(f"{row['player_name']} did not retain all 131 starts")
        original = original_career.filter(pl.col("player_id") == row["player_id"])
        if original.height != 1:
            raise AssertionError("Player not found in original validated career summary")
        ref = original.row(0, named=True)
        close(row["annual_relative_qb_epa_per_dropback"], ref["relative_qb_epa_per_dropback"], f"{row['player_name']} original relative EPA")
        close(row["qb_epa_per_dropback"], ref["qb_epa_per_dropback"], f"{row['player_name']} original absolute EPA")
        print(
            f"{row['player_name']}: {row['starts']} starts | {int(row['usable_dropbacks']):,} DB | "
            f"annual relative {row['annual_relative_qb_epa_per_dropback']:+.4f} | "
            f"3-year relative {row['three_year_relative_qb_epa_per_dropback']:+.4f}"
        )
    for row in by_season.iter_rows(named=True):
        ref = original_seasons.filter(
            (pl.col("player_id") == row["player_id"]) & (pl.col("season") == row["season"])
        )
        if ref.height != 1:
            raise AssertionError(f"Missing player/season: {row['player_name']} {row['season']}")
        ref_row = ref.row(0, named=True)
        close(
            row["annual_relative_qb_epa_per_dropback"],
            ref_row["relative_qb_epa_per_dropback"],
            "original season-relative EPA",
        )
    audit = windows.select(
        "season", "window_seasons", "window_kind", "provisional_partial_window",
        "window_season_count", "window_league_usable_dropbacks",
        "three_year_league_qb_epa_per_dropback", "annual_league_qb_epa_per_dropback",
    ).join(
        by_season.select("season", "player_name", "starts", "usable_dropbacks", "annual_relative_qb_epa_per_dropback", "three_year_relative_qb_epa_per_dropback"),
        on="season", how="inner", validate="1:1",
    ).sort("season")
    if audit.height != 20:
        raise AssertionError("Audit is missing study seasons")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    for df, path in ((windows, LEAGUE_OUTPUT), (enriched, GAMES_OUTPUT), (by_season, SEASON_OUTPUT), (career, CAREER_OUTPUT)):
        df.write_parquet(path)
        df.write_csv(path.with_suffix(".csv"))
    audit.write_csv(AUDIT_OUTPUT)
    print("\nPASS: 20 window baselines | 262 study games | 20 player-seasons | 2 careers")
    print(f"Three-year league baselines: {LEAGUE_OUTPUT}")
    print(f"First 131 starts: {CAREER_OUTPUT}")
    print(f"Audit: {AUDIT_OUTPUT}")


if __name__ == "__main__":
    main()
