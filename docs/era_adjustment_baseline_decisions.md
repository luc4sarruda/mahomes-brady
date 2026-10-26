# Era-Adjusted Analysis — NFL Dropback Baseline Decisions

## Scope and research objective

The objective is to compare Tom Brady and Patrick Mahomes over their first 131 regular-season starts using season-specific NFL benchmarks. This document describes the construction of **league-level** quarterback EPA/dropback baselines. Player-level EPA and relative EPA/dropback will be computed in a subsequent reproducible processing step, applying the **same** play eligibility rules.

## Historical dropback indicator inconsistency

The nflfastR data include `qb_scramble` and `qb_dropback` indicators. In early seasons, historical scramble corrections were applied to `qb_scramble` after `qb_dropback` had already been derived. As a consequence, some run plays flagged as scrambles have `qb_dropback = 0`.

The user's 2001–2007 audit found these counts of explicitly flagged scramble runs absent from the original dropback population: **308 (2001), 270 (2002), 658 (2003), 711 (2004), 532 (2005), 0 (2006), and 0 (2007)**. These 2,479 records are historical audit candidates; the final baseline filter must recheck all eligibility conditions on the source records. These figures do not imply that every other quarterback rush was a scramble.

The revised dropback indicator is:

```
corrected_dropback = (
    qb_dropback == 1
    or (play_type == "run" and qb_scramble == 1)
)
```

Eligible plays additionally require `two_point_attempt != 1`, `qb_spike != 1`, and `qb_kneel != 1`. A play matching both branches is counted only once. The original raw flags are **not overwritten**.

## Season baselines

- Source: complete nflverse/nflfastR play-by-play for every included regular season.
- Years: 2001–2010 and 2017–2026, as determined by the study table.
- Regular seasons 2001–2010 and 2017–2025: full-season league-wide games, even where the study player started only a subset of games in that season.
- 2026: a **partial season**, restricted to league games with `game_date` on or before the last study-game date; not merely to a maximum week number. Same-day games may still include kickoffs later than the study game, since the cutoff is by calendar date.
- Numerator: sum of finite `qb_epa` values on eligible dropbacks.
- Denominator: number of eligible dropbacks with finite `qb_epa` (play-weighted mean, **not** an unweighted mean of quarterback averages).
- Report separately all eligible plays and all usable EPA plays. Exclude missing EPA values from both numerator and denominator; **do not impute zero**.
- Track the sample standard deviation and rate of positive `qb_epa` as descriptive attributes; they do not by themselves produce a fully era- or context-controlled comparison.

### Explicitly documented missing EPA observation

The existing data audit found `2019_01_PIT_NE`, play ID 4166, a Ben Roethlisberger pass without `qb_epa`. The baseline-builder excludes this specific observation from EPA calculations and reports it. Unexpected missing EPA values block export pending investigation.

## Player identification

The `passer_player_id` field can be absent on scrambles. For subsequent QB-level work, the verified fallback sequence is `passer_id`, then `passer_player_id`, then `rusher_player_id` **only on scrambles**. The league baseline is computed over plays regardless of which quarterback is involved, but resolved IDs are audited to ensure the same source can support per-player calculations.

## Outputs and validation

Run `python3 scripts/build_nfl_epa_baselines.py` at the repository root. The script reads the existing study table and cached league play-by-play files. Outputs:

- `data/processed/nfl_season_dropback_baselines.parquet`
- `data/processed/nfl_season_dropback_baselines.csv`
- `reports/validation/era_baseline_quality_audit.csv`
- `reports/validation/era_baseline_missing_epa_plays.csv` if missing observations exist

The pipeline checks the expected regular-season league game counts, coverage of study games, duplicate play IDs, restored-scramble partition, missing QB identifiers, and missing EPA allowlist. Outputs are not marked validated until the script runs successfully on the local dataset.

## Interpretation and limitations

League QB EPA/dropback varies with rule changes, offensive strategies, defenses, and model assumptions. Subtracting the season baseline reduces one major temporal confounder but **does not isolate individual quarterback talent**: opponent strength, team context, game situation, and era-dependent coverage of scramble flags remain limitations. Play-by-play `qb_epa` also contains effects from teammates, including receivers and blocking. Later work should include sensitivity checks (e.g., standardized scores and alternative baseline definitions) before making strong cross-era performance claims.

## References

- nflfastR field documentation: https://nflfastr.com/reference/fast_scraper.html
- nflfastR change history: https://nflfastr.com/news/index.html
- nflfastR historical scramble-fix code: https://rdrr.io/cran/nflfastR/src/R/helper_add_nflscrapr_mutations.R
- nflfastR beginners' guide (QB EPA): https://nflfastr.com/articles/beginners_guide
