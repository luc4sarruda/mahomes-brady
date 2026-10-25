# Passing Statistics — Validation Protocol

**Project:** *Can the Baby GOAT Surpass the GOAT?*  
**Scope:** Tom Brady and Patrick Mahomes, first 131 regular-season starts each  
**Document status:** Automated full-sample cross-pipeline audit passed (user-reported); independent box-score audit not fully documented  
**Date:** October 25, 2026

## 1. Purpose

Validate the passing statistics derived from nflverse play-by-play (PBP) before publishing cross-era comparisons. A passing-statistics script that executes successfully is **not sufficient evidence** that its outputs are correct. Two spot checks caught methodological issues earlier; a wider audit is required to detect issues outside those specific games and seasons.

**Dataset under review:** `data/processed/qb_game_stats.parquet` (262 player-game observations).

**Metrics:** official-style passing attempts, completions, passing yards, passing touchdowns, and interceptions.

**Important distinction:** A start belongs to the *starting* quarterback, but individual passing attempts belong to the *actual passer*. Brady started `2005_17_MIA_NE` but Matt Cassel later played; Cassel's attempts are **not** Brady's attempts.

## 2. Metric Definitions

| Derived field | Working definition | Important exceptions |
|---|---|---|
| `attempts` | Official-style pass attempts credited to the QB | Clock-stopping QB spikes count; sacks, scrambles, and two-point tries do not |
| `completions` | Completed official pass attempts | Spikes are incomplete |
| `passing_yards` | Passing yards credited to the QB | Do not credit receiving YAC twice or add sack yards |
| `passing_tds` | Passing touchdowns credited to the QB | Do not count rushing touchdowns |
| `interceptions` | Interceptions thrown by the QB | Do not count fumbles as interceptions |
| `completion_pct` | `100 * completions / attempts` | Undefined when attempts = 0 |
| `yards_per_attempt` | `passing_yards / attempts` | Undefined when attempts = 0 |
| `td_rate` | `100 * passing_tds / attempts` | Undefined when attempts = 0 |
| `int_rate` | `100 * interceptions / attempts` | Undefined when attempts = 0 |

Treat these as the project's working definitions; they must be reconciled to independently reported NFL box scores. No rounding is permitted when comparing the five **integer** totals.

## 3. Validation Levels

### Level A — Internal integrity (all 262 rows)

- Exactly 131 starts per player and 262 unique `(player_id, game_id)` pairs.
- Every passing-statistics row matches exactly one master-table row.
- No missing or negative count metrics; `completions <= attempts`, `TDs <= attempts`, `INTs <= attempts`.
- All joins use both the player and the game; a teammate's throws must not be assigned to the starter.
- Inspect games with zero attempts, QB substitutions, spikes, missing player IDs, and unusual statistical plays.
- Verify arithmetic for all derived percentages; rates with `attempts = 0` should be null, not zero.

### Level B — Full cross-pipeline comparison (all 262 rows)

Use `nflreadpy.load_player_stats(seasons=[...], summary_level='week')` and join to the master sample on **both** `player_id` and `game_id`. Filter `season_type == 'REG'`.

**Every metric must match exactly**, yielding up to `262 × 5 = 1,310` integer comparisons. The script `scripts/validate_passing_stats.py`:

1. Downloads the weekly player-stat releases (cached locally for repeatability).
2. Matches weekly reference records to all 262 starts.
3. Produces an all-games comparison CSV and a discrepancies-only CSV.
4. Fails when any weekly reference record is absent or any metric differs.
5. Writes a summary and a reproducible template for independent checks.

**Caveat:** Weekly player stats and the underlying PBP originate from the nflverse ecosystem. Agreement is a valuable *cross-pipeline consistency test*, **not** fully independent confirmation of the raw data or NFL scoring decisions.

### Level C — Independent NFL / Pro Football Reference review

Cross-check an **externally sourced** sample of box scores from [NFL.com](https://www.nfl.com/) or [Pro Football Reference](https://www.pro-football-reference.com/). The script generates `reports/validation/official_boxscore_review_template.csv` with:

- At least one seeded, randomly selected start from each player-season in the sample (20 player-season groups, barring absent groups).
- The known Brady/Cassel exception `2005_17_MIA_NE`.
- Every start with zero derived attempts, if any.
- Additional exceptional cases (especially a documented spike play and a game with QB substitution) should be added if not already selected.

Record a **direct box-score URL** and its five official counts in the review sheet. Do not mark the external audit as passed until all reviewed rows agree, or discrepancies are investigated and resolved.

This sampling strategy provides coverage across both players and all represented seasons, but it **does not prove** that every unreviewed source record is correct. For complete independent verification, all 262 games would need independent checks.

## 4. Important Known Cases

### DQ-001 — Brady/Cassel starting-quarterback attribution

- Game: `2005_17_MIA_NE` (January 1, 2006).
- Brady started; Cassel replaced him.
- The derived master table corrects the **starter identity only**.
- Passing statistics remain attached to the quarterback who threw each attempt.
- Reported independent spot check: Brady had 8 attempts, 3 completions, 37 yards, 1 passing TD, 1 interception.

### DQ-003 — QB spike classification

- During initial validation, Mahomes's 2018 PBP-derived passing total was 579 attempts, compared with the NFL's 580.
- Completions (383), yards (5,097), TDs (50), and INTs (12) matched.
- The corrected extraction includes official clock-stopping quarterback spikes as incomplete attempts.
- The local rerun reportedly passed the Mahomes 2018 totals check.
- **Required follow-up:** confirm the specific spike's `game_id`/`play_id` from the raw PBP and ensure the same classification works across the full sample. Do not infer that there are no additional issues from one successful season check.

## 5. Special Comparability Warnings

- **Season totals ≠ 131-start sample totals.** Brady appeared as a *reserve* on September 23, 2001, before his first start. The 2001 official full-season totals include those attempts, but our study's start-based subset must not. Likewise, Brady's 2010 and Mahomes's 2026 study windows stop during the regular season.
- The starter identified by the game schedule need not play every QB snap.
- A zero in the computed game table can mean a genuine zero, a missing player attribution, or a failed join. It must be investigated rather than assumed accurate.
- A clean join, a plausible total, or agreement with another nflverse-derived table is not a guarantee of independent source accuracy.

## 6. Audit Outputs

| File | Meaning |
|---|---|
| `reports/validation/passing_game_comparison.csv` | All 262 PBP-derived versus weekly-player-stat comparisons |
| `reports/validation/passing_discrepancies.csv` | Missing reference rows and mismatched metrics |
| `reports/validation/official_boxscore_review_template.csv` | Selected games and blank fields for official external reference values |
| `reports/validation/passing_validation_summary.md` | Dated audit results and limitations |

**Acceptance criteria:**

- [x] All 262 internal rows pass integrity rules (user-reported script result).
- [x] All available weekly reference rows match, with no unexplained missing references (user-reported script result).
- [ ] External box scores checked for the stratified sample across both players and all seasons.
- [ ] All discovered mismatches resolved or explicitly marked as accepted limitations.
- [ ] Research notes and the data quality log updated with source URLs and rerun results.

## 7. Reproduction

```bash
python3 scripts/create_master_table.py
python3 scripts/create_player_stats.py
python3 scripts/validate_passing_stats.py
```

The weekly reference data are cached under `data/raw/player_stats/`. Preserve the snapshot needed to replicate published findings and record file hashes and package versions. Raw data should remain unchanged.

## 8. References

- [nflreadpy — Load functions](https://nflreadpy.nflverse.com/api/load_functions/)
- [nflverse — Player statistics dictionary](https://nflreadr.nflverse.com/articles/dictionary_player_stats.html)
- [nflfastR — Statistics definitions](https://nflfastr.com/articles/stats_variables.html)
- [NFL — Tom Brady 2001 game logs](https://www.nfl.com/players/tom-brady/stats/logs/2001/)
- [Pro Football Reference](https://www.pro-football-reference.com/)


## Execution Update — October 25, 2026

The user reports the automated validation passed with 100% agreement across all selected starts and manually checked several games with no discrepancies. The exact manual sample, source URLs, validation summary, and data snapshot metadata must still be recorded. This is a user-reported pipeline result, not an independent rerun.
