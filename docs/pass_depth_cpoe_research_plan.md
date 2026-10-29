# Pass Depth, Efficiency, and CPOE — Research Plan

## Research question

How did Tom Brady and Patrick Mahomes distribute their passing attempts across target depths, and how efficiently did they perform compared with model-expected completion probability?

## Fixed study windows

The primary comparison **preserves the previously validated first-131-start cohorts** and includes only:

- Tom Brady: 2006–2010, within his first 131 regular-season starts (16 in 2006, 16 in 2007, 1 in 2008, 16 in 2009, 4 in 2010; **53 starts**).
- Patrick Mahomes: 2018–2021, within his first 131 regular-season starts (16 in 2018, 14 in 2019, 15 in 2020, 17 in 2021; **62 starts**).

These are **availability- and context-defined windows**, not objectively selected "best" seasons. A future sensitivity analysis may use full regular seasons, but it must be labeled as a different sample. Never mix full-season Brady 2010 data into the first-131-start comparison.

## Depth bins (air yards, not final gain)

| Label | Rule |
|---|---|
| Behind LOS | air_yards < 0 |
| 0–5 | 0 <= air_yards < 6 |
| 6–10 | 6 <= air_yards < 11 |
| 11–19 | 11 <= air_yards < 20 |
| 20+ | air_yards >= 20 |

The `11–19` bin avoids an overlap at 20 yards with `20+`.

## Metrics and denominators

1. **Attempt share**: attempts in a zone / all attempts with a valid target depth. Publish `air_yards` coverage against official attempts; do not silently pretend uncharted attempts have zero depth.
2. **Completion %**: completions / attempts in the target-depth zone. Use all charted passes with a valid completion indicator.
3. **QB EPA per attempt**: sum of `qb_epa` / attempts with a valid `qb_epa` in the zone. This is *throw EPA*, not EPA per dropback; exclude sacks and scrambles.
4. **CPOE (percentage points)**: 100 × mean(`complete_pass` − `cp`) among attempts with valid `air_yards`, `cp`, and `complete_pass`. Report the *modeled* sample size and compare `cpoe` source field for unit consistency. Never impute missing completion probabilities or treat missing values as zero.

A useful supplementary statistic is **expected completion %** = 100 × mean(`cp`) on the exact CPOE-eligible attempts. Its denominator must match the actual completion percentage shown beside it.

## Eligibility and attribution

- Regular-season starts only, matching the validated master table.
- Attribute throws to the actual passer by (`game_id`, `passer_player_id`, `posteam`), not merely to the team's starter.
- Preserve official pass attempts for reconciliation; exclude spikes and any throws with no meaningful charted target depth from depth-zone metrics rather than inventing an air-yards value.
- Exclude sacks, scrambles, and two-point attempts from throw-depth comparisons.
- Cross-check pass counts against `qb_game_stats.parquet` and review any discrepancy before producing analysis tables.

## CPOE interpretation caveats

The nflfastR CP model is available back to 2006, but its features and era treatment differ from NFL Next Gen Stats tracking-based xCOMP. CPOE controls for certain *measured* conditions (such as target depth), but is not a direct measure of improvisation, pressure management, or the quarterback's contribution independent of receivers, scheme, or opponent. Verify sample coverage and calibration before interpreting fine-grained bins. Deep throws are relatively infrequent; report attempts and avoid over-interpreting small samples.

## Execution order

1. Run `python3 scripts/inspect_pass_depth_cpoe.py`.
2. Review `reports/validation/pass_depth_cpoe_coverage_by_season.csv`, `pass_depth_cpoe_zone_audit.csv`, and `pass_depth_cpoe_unit_check.csv`.
3. Only after coverage and counts are validated, construct the final pass-depth metrics, optional era-specific league benchmarks, and a new notebook `04_pass_depth_and_accuracy.ipynb`.

## Primary source

- nflfastR README: https://github.com/nflverse/nflfastR (CP/CPOE available from 2006).
- Open Source Football CP model documentation: https://opensourcefootball.com/posts/2020-09-28-nflfastr-ep-wp-and-cp-models/
