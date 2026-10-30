# CPOE Robustness: Season Patterns, Direct Differences, and 2007 Sensitivity

## Research question

Did Tom Brady's observed CPOE advantage over Patrick Mahomes on passes of 6–10 air yards persist outside Brady's 2007 season? How sensitive are the depth-specific Brady–Mahomes differences to game-to-game variation?

## Scope and inputs

- Brady: 53 selected regular-season starts, 2006–2010, within his first 131 starts. The sample contains one start in 2008 and four starts in 2010.
- Mahomes: 62 selected regular-season starts, 2018–2021, within his first 131 starts.
- Input files from the validated pass-depth pipeline: `qb_pass_depth_summary.parquet`, `qb_pass_depth_by_season.parquet`, `qb_pass_depth_by_game.parquet`.
- All statistics concern passing attempts with valid depth and (for CPOE) a valid completion-probability estimate. Passes without `cp` are not imputed. Pass depth is **air yards**, not yards gained after the catch.
- Depth zones: Behind LOS, 0–5, 6–10, 11–19, and 20+.

## CPOE aggregation

For modeled throw *i*, the CPOE residual in percentage points is:

`r_i = 100 × (complete_pass_i − cp_i)`

For any player, season, or depth zone:

`CPOE = (sum_i r_i) / number_of_modeled_attempts`

This is **throw-weighted**. Do not take an unweighted mean of game-level or season-level CPOE values.

For each depth zone, the direct observed difference is:

`Delta = CPOE_Brady − CPOE_Mahomes`

Positive values favor Brady; negative values favor Mahomes on **model-relative completion**, not necessarily overall quarterback value.

## Exploratory game-cluster bootstrap

1. For each player, collect all study games, with the zone's modeled-attempt count and summed CPOE residual for that game. Include a game with zero modeled attempts in the zone with both sufficient statistics set to zero.
2. Independently sample Brady games with replacement and Mahomes games with replacement, keeping each cohort's original game count (53 and 62 in the full analysis).
3. Pool modeled attempts and summed CPOE residuals within each resample, and calculate the difference between the two pooled CPOEs.
4. Repeat 10,000 times using explicitly documented random seeds. Report the 2.5th and 97.5th percentiles of the resampled **differences**.
5. Run the same method for each of the five zones. This is different from inferring a direct difference from overlap of separate quarterback intervals.

The interval is exploratory. It does not adjust for trying five depth zones, comparing different historical eras, differing receiver or opponent quality, uncertainty in the completion-probability model, or season-level dependence beyond the sampled game clusters. It is **not** proof of causation or an estimate of intrinsic quarterback talent.

## Season-specific patterns

- Figure 19 plots season-by-depth CPOE for the two periods, labeling each cell with modeled-attempt count.
- Cells with fewer than 30 modeled throws are displayed in neutral gray to avoid visually exaggerating noisy values. This **30-attempt display threshold is not an exclusion from pooled estimates or bootstrap calculations**.
- Color intensity is clipped at ±15 percentage points for readability; numerical annotations show actual values for adequately sampled cells.

## 2007 sensitivity and leave-one-season-out checks

The primary sensitivity comparison removes **only Brady's 2007 study starts**; Mahomes's original study window remains unchanged. Additional rows remove each Brady study season in turn. For every altered comparison, the direct difference and its bootstrap interval are recomputed.

Removing a season changes the target sample and does not estimate a counterfactual career. In particular, comparing a different number of Brady and Mahomes starts is a descriptive design choice, not a balanced causal comparison.

## Outputs

The updated `04_pass_depth_and_accuracy.ipynb` adds:

- `reports/figures/19_cpoe_by_season_and_depth.png`
- `reports/figures/20_cpoe_direct_differences_bootstrap.png`
- `reports/pass_depth_cpoe_direct_contrasts.csv`
- `reports/pass_depth_cpoe_6_10_leave_one_season_out.csv`

## Validation and limitations

- The notebook rechecks that both players' game-level sufficient statistics reproduce the original pooled CPOE within floating-point precision.
- The 2007-excluded pooled estimate is independently checked against the season-level sufficient statistics.
- These results measure model-relative completion rather than decision quality, offensive contribution, or playmaking under pressure.
- Historical model calibration, missing `cp` predictions (different rates by player), and different roster/scheme contexts may affect cross-era comparisons.
- Findings for multiple zones should be framed as exploratory; consider pre-registering a 6–10-yard primary contrast before subsequent hypothesis testing.
