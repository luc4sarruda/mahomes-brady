# Era-Adjusted Quarterback EPA — Study-Level Methodology

## Purpose

This step estimates quarterback-attributed EPA on **each of the 262 selected regular-season starts** (131 for Tom Brady and 131 for Patrick Mahomes), then compares those results to **NFL dropback-level baselines for the same season**. The objective is an era-aware, descriptive comparison, **not** a causal estimate of quarterback ability.

## Required inputs

- `data/processed/qb_complete_stats.parquet`: validated 262-start study sample, keyed by `(player_id, game_id)`.
- `data/raw/play_by_play/pbp_{season}.parquet`: cached nflverse/nflfastR play-by-play for all league regular-season games in 2001–2010 and 2017–2026.
- `data/processed/nfl_season_dropback_baselines.parquet`: 20 audited NFL dropback baselines.
- `scripts/build_nfl_epa_baselines.py`: **the same, already-validated implementation** that produced the league baselines. The player script imports `load_study` and `load_eligible_dropbacks` directly from this file to avoid divergent eligibility rules.

Run from the repository root:

```bash
python3 scripts/build_qb_era_adjusted_stats.py
```

## Dropback eligibility and attribution

The script reuses the league baseline's exact rule:

```text
eligible = (
    qb_dropback == 1
    OR (play_type == "run" AND qb_scramble == 1)
) AND two_point_attempt != 1 AND qb_spike != 1 AND qb_kneel != 1
```

Each qualifying play is counted once. The `qb_scramble` branch restores historical scrambles missing from `qb_dropback`, especially in 2001–2005. An eligible quarterback ID is resolved by the baseline builder using `passer_id`, then `passer_player_id`, then `rusher_player_id` only for scrambles. Player plays are joined to study starts on `game_id` and included only when `resolved_qb_id == player_id` **and** `posteam == team`. This prevents crediting a starter with dropbacks taken by a substitute QB.

The source `qb_epa` variable is used rather than ordinary `epa`: the nflfastR adjustment treats certain completed passes followed by receiver fumbles differently. It is nevertheless **not an independent measurement of talent**.

## Per-start estimands

For each study QB start `g` in season `s`:

- `usable_dropbacks_g`: qualifying dropbacks with finite `qb_epa`.
- `qb_epa_sum_g = sum(qb_epa on qualifying player plays)`.
- `qb_epa_per_dropback_g = qb_epa_sum_g / usable_dropbacks_g`.
- `league_qb_epa_per_dropback_s`: the season's **play-weighted NFL baseline**.
- `relative_qb_epa_per_dropback_g = qb_epa_per_dropback_g - league_qb_epa_per_dropback_s`.
- `relative_qb_epa_total_g = qb_epa_sum_g - usable_dropbacks_g * league_qb_epa_per_dropback_s`.
- `qb_epa_success_rate_g`: share of usable dropbacks with `qb_epa > 0`.
- `relative_qb_epa_success_rate_pp_g`: `(player_success_rate - league_success_rate_s) * 100` percentage points.

Historical scramble indicators are reported as audit fields, not manually redefined.

## Aggregation across starts and seasons

**Never average the per-game EPA/dropback values without weighting.** The correct first-131-start relative EPA/dropback is:

```text
sum(relative_qb_epa_total_g) / sum(usable_dropbacks_g)
```

Equivalently:

```text
sum(qb_epa_sum_g) / sum(usable_dropbacks_g)
-
sum(usable_dropbacks_g * league_baseline_s) / sum(usable_dropbacks_g)
```

The study-season summary includes **only the selected starts within that season** (e.g., Brady's single selected 2008 start), not the quarterback's entire NFL season. The NFL baseline itself uses the full regular season for completed historical seasons. **2026 is partial:** its baseline ends on 2026-10-18, the last study date, including all league games on that calendar date.

## Quality gates

The script fails before writing final outputs if any of the following occur:

1. Missing/duplicated study players, seasons, games, or baselines.
2. Baseline population, sum, mean, or positive-EPA rate differs when recreated from source PBP.
3. Missing study games or selected QB dropbacks; duplicated source play keys.
4. An eligible study-QB dropback cannot be attributed to the selected player and offense.
5. Any eligible selected-QB play has missing/nonfinite EPA.
6. Game totals do not reconcile to play totals, or career summaries do not contain exactly 131 starts each.
7. Season-relative EPA arithmetic does not reconcile with player EPA minus expected league EPA.

The baseline's one known missing EPA observation (`2019_01_PIT_NE`, play 4166, Ben Roethlisberger) is excluded at the league level. It is not a Brady or Mahomes play.

## Outputs

| Path | Grain | Purpose |
|---|---|---|
| `data/processed/qb_era_dropback_plays.parquet` | QB × game × play | Play-level audit of attributed dropbacks |
| `data/processed/qb_game_era_adjusted.parquet` and `.csv` | QB × game | 262 era-adjusted game records |
| `data/processed/qb_study_season_era_summary.parquet` and `.csv` | QB × season in the selected starts | Season segments within the study |
| `data/processed/qb_first_131_era_summary.parquet` and `.csv` | QB | Correctly weighted 131-start comparison |
| `reports/validation/qb_era_adjustment_quality_audit.csv` | Season | Audit counts and reconstruction details |

## Interpretation and limitations

- Subtracting a season baseline **partially adjusts for era** but does not isolate QB performance from teammates, play-calling, defenses, field position, game state, opponent quality, or differences in the underlying EPA model.
- The league baselines include study players' dropbacks. A leave-one-player-out benchmark could be investigated as a sensitivity analysis, but is not used here.
- Brady's 2008 study season and Mahomes's 2017 study season contain only one start. Their study-season relative figures should not be mistaken for full-season estimates.
- The 2026 benchmark is incomplete and should be marked as provisional. Historical scramble coverage was corrected using existing nflfastR tags, not hand-coded interpretations of play descriptions.
- A positive relative EPA/dropback means the selected QB's EPA per qualifying dropback exceeded the **season's play-weighted league mean**; it does not, by itself, establish who is a better quarterback.

## Suggested next phase

After running the script successfully, create `notebooks/03_era_adjusted_analysis.ipynb` for visual comparisons of game-level and aggregated season-relative efficiency. Begin with the first-131-start weighted relative EPA/dropback values, then investigate season segments, sample size, and robustness.

## References

- nflfastR QB EPA explanation: https://www.nflfastr.com/articles/beginners_guide
- nflfastR `add_qb_epa`: https://nflfastr.com/reference/add_qb_epa.html
- Project-specific league baseline decisions: `docs/era_adjustment_baseline_decisions.md`
