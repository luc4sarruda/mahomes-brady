# Era-Adjusted Quarterback Efficiency — Methodology (Draft)

## Research question
How do Tom Brady and Patrick Mahomes compare relative to league-wide quarterback efficiency during their respective seasons, within their first 131 regular-season starts?

## Study sample
- 131 starts per quarterback (262 quarterback-game observations).
- Quarterback sample is fixed by `data/processed/qb_complete_stats.parquet`.
- Regular season only; playoffs excluded.
- Source play-by-play: `data/raw/play_by_play/pbp_{season}.parquet`.

## Primary metric: relative QB EPA per dropback

```
QB EPA/DB = sum(qb_epa for eligible QB dropbacks) / number of eligible QB dropbacks
League QB EPA/DB = sum(qb_epa for eligible league dropbacks in season) / number of eligible league dropbacks in season
Relative QB EPA/DB = QB EPA/DB - League QB EPA/DB
```

The league baseline is *dropback weighted*, not the unweighted average of individual quarterback rates. Both the player numerator and the league baseline use the same play-level variable and eligibility rule. Values above zero indicate above-league-mean performance by this metric.

`qb_epa` differs from ordinary `epa` on some completions followed by lost receiver fumbles, making it more appropriate for QB-oriented attribution. Source: nflfastR documentation.

## Eligible dropbacks
- `qb_dropback == 1` (passes, sacks, scrambles).
- `season_type == 'REG'`.
- Exclude two-point attempts, spikes and kneel-downs.
- Assess missing `qb_epa` and passer identification before finalizing the denominator.
- Designed quarterback runs are **not** dropbacks. They require a separate rushing metric.
- Do not infer an eligible dropback from an official passing attempt: spikes are official passing attempts but not analytical dropbacks.

## Era baseline boundaries
- For historical completed seasons, use all eligible NFL regular-season games in that season.
- For the incomplete 2026 season, initially limit the reference to weeks through Mahomes's final included start. Document the data snapshot and missing/unfinished games. Recompute whenever source data change.
- Consider a robustness check using week-matched historical reference windows to address any bias from partial-season QB samples.

## Data quality checks before baseline construction
1. Confirm that cached PBP files contain the **entire NFL league** for each season, rather than only games in the 262-start sample.
2. Confirm complete coverage of each quarterback's sampled games.
3. Quantify the fraction of eligible dropbacks without `qb_epa` or `passer_player_id`.
4. Inspect the treatment of historical scrambles, sacks, plays with penalties and receiver fumbles.
5. Confirm that every sampled play belongs to exactly one QB start, where attribution is possible.
6. Compare per-game QB dropbacks against passing attempts + sacks + scrambles (accounting for spikes and any source-definition differences); investigate mismatches.

## Interpretation limits
Relative QB EPA/DB adjusts for a season's NFL average, but does not fully remove opponent strength, offensive line/receiver quality, scheme, game situation, or all differences between eras. These effects require separate analyses. Never present the difference in relative EPA as the isolated causal contribution of the quarterback.

## Planned project outputs
- `reports/validation/era_pbp_source_audit.csv` (first step)
- `data/processed/nfl_season_dropback_baselines.parquet` (after source validation)
- `data/processed/qb_era_adjusted_stats.parquet` (after sample attribution validation)
- `notebooks/03_era_adjusted_analysis.ipynb` (interpretation and visualization)

## Status
**Methodology draft; source audit pending execution.** No era-adjusted results have yet been calculated or validated.
