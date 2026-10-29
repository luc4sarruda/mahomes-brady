# Pass Depth & Completion Percentage Over Expected (CPOE)

## Study design

**Research question:** How did Tom Brady and Patrick Mahomes distribute and execute their regular-season passes across target depths, and how much better or worse did they complete passes than the nflfastR model expected?

The primary study keeps the original first-131-start sampling framework and restricts players to CPOE-available years:

| Quarterback | Study years | Included starts | Official attempts | Attempts with known depth | CPOE modeled attempts |
|---|---|---:|---:|---:|---:|
| Tom Brady | 2006–2010 | 53 | 1,793 | 1,793 | 1,767 |
| Patrick Mahomes | 2018–2021 | 62 | 2,310 | 2,309 | 2,221 |
| **Total** | | **115** | **4,103** | **4,102** | **3,988** |

Brady 2008 contributes **one start**; Brady 2010 contributes **four starts**. These samples are chosen because the nflfastR completion-probability model is available beginning in 2006 and the windows support a roster-era research question; they are not objectively identified as each player's best period.

## Selection rules and data provenance

- Source: nflverse/nflfastR play-by-play (PBP), previously downloaded, used only for game IDs in `qb_first_131_starts.parquet`.
- Selection and QB attribution reuse the audited functions from `scripts/inspect_pass_depth_cpoe.py`, which match the validated pass-attempt pipeline.
- Official-style pass attempts are reconciled at **player/game** level with `data/processed/qb_game_stats.parquet`, including clock-stopping spikes.
- Passes are assigned to the actual passer ID and offensive team (not merely to the starter of record).
- Do not include sacks, scrambles, or two-point attempts as throws. A spike remains an official attempt but may not have charted depth or CP.
- `air_yards` defines target depth rather than total gained yards after catch.

### Non-overlapping depth bins

| Bin | Air yards |
|---|---|
| Behind LOS | `< 0` |
| 0–5 | `0 <= air_yards < 6` |
| 6–10 | `6 <= air_yards < 11` |
| 11–19 | `11 <= air_yards < 20` |
| 20+ | `air_yards >= 20` |

## Metrics

1. **Attempt Share (%):** `100 × attempts in zone / all attempts with charted air_yards (for that QB and analysis window)`.
2. **Completion %:** `100 × completions in zone / all attempts in zone with charted air_yards`.
3. **QB EPA per Attempt:** `sum(qb_epa) / count(valid qb_epa)` on charted pass attempts in each zone. This is **NOT** total quarterback EPA per dropback: sacks and scrambles are excluded, as are throws without charted depth.
4. **Expected Completion % (modeled set):** `100 × sum(cp) / count(valid cp + completion + depth)`.
5. **Observed Completion % (modeled set):** `100 × sum(complete_pass) / count(valid cp + completion + depth)`.
6. **CPOE (percentage points):** `100 × [sum(complete_pass) − sum(cp)] / count(valid cp + completion + depth)`; equivalent to the mean of nflfastR per-play `cpoe` in the usable modeled subset.

The difference between observed completion percentage in the full depth sample and observed completion percentage among the **CP modeled** subset is intentional. Do not subtract the modeled expected completion percentage from the broader observed percentage; doing so mixes denominators.

**No imputation:** throws with missing depth are not assigned to any zone; throws without CP count toward attempt share and observed completion percentage but not CPOE. Report CP coverage separately for each player, zone, and season.

## Quality evidence and checks

From `inspect_pass_depth_cpoe.py`:
- 4,103 official attempts reconciled; 4,102 charted depths (one 2020 Mahomes attempt has missing depth).
- 3,988 attempts have both charted depth and CP/CPOE data; **97.22% coverage among charted attempts**.
- Brady CPOE availability: 1,767 / 1,793 (~98.55% of official attempts).
- Mahomes CPOE availability: 2,221 / 2,310 (~96.15%).
- Recomputed `100 × (complete_pass − cp)` matches source CPOE with mean absolute error 0.0 on the 3,988 modeled passes.

From `build_pass_depth_cpoe.py` (to be validated after local execution):
- Repeat player/game official-attempt reconciliation, no changes to source stats.
- Check CP bounds, completion flags, source CPOE identity, and minimum depth/CP/EPA coverage.
- Check per-zone/season/game sums against the same underlying charted attempts.
- Check the aggregated CPOE identity `CPOE = observed modeled completion % − expected modeled completion %`.
- Preserve one uncharted pass in a separate report.

## Statistical uncertainty

The notebook uses nonparametric game-cluster bootstrapping: resample individual games **within each player's selected period**, retaining all throws in a sampled game, and compute CPOE by depth using sufficient statistics (`sum_cpoe_pp`, `modeled_attempts`). The displayed percentile intervals are descriptive and do not correct for all systematic sources of bias or dependence across seasons.

Season-specific small-sample CPOE (especially Brady's single game in 2008 and 2010's four selected starts) should not be interpreted as stable performance. Pooled stats are **weighted by qualifying attempts**, not average-of-season-rates.

## Interpretation constraints

- CPOE adjusts for the model's **observed predictive features**; it is not a direct measurement of improvisation, arm strength, pure quarterback accuracy, or individual causal contribution. Receivers, protection, scheme, and opponents can influence outcomes.
- Public nflfastR CP is not NFL Next Gen Stats tracking-data xCOMP. Historical model calibration may vary by year/era.
- Passing EPA/attempt and CPOE answer different questions: completing difficult throws does not necessarily maximize EPA, and safe short completions may still produce offensive value via YAC.
- For strong cross-era claims, separately check calibration on league throws in 2006–2010 and 2018–2021, grouped by depth and season.
- The study deliberately avoids a full-season comparison for Brady 2010 and avoids implying the 53- vs 62-start cohorts are equally sized.

## Outputs

- `data/processed/qb_pass_depth_attempts.parquet`: individual validated throws and eligibility flags.
- `data/processed/qb_pass_depth_by_game.parquet`: sufficient statistics for game-cluster bootstrap.
- `data/processed/qb_pass_depth_by_season.parquet` / `.csv`: season-zone metrics.
- `data/processed/qb_pass_depth_summary.parquet` / `.csv`: pooled player-zone metrics.
- `reports/validation/pass_depth_build_quality_summary.csv`: coverage and denominator audit.
- `reports/validation/pass_depth_uncharted_attempts.csv`: generated if an attempt lacks target depth.
- `reports/pass_depth_cpoe_summary_with_intervals.csv`: pooled results plus exploratory game-bootstrap intervals (notebook).
- `reports/figures/14_*.png` ... `18_*.png`: notebook figures.

## References

- nflfastR project and field availability: https://github.com/nflverse/nflfastR
- nflfastR reference manual (`cp`, `cpoe`, `qb_epa`): https://nflverse.r-universe.dev/nflfastR/doc/manual.html
- nflfastR guide on QB EPA: https://www.nflfastr.com/articles/beginners_guide
