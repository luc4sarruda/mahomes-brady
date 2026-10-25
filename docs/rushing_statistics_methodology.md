# Rushing, Mobility, and Sacks — Methodology

**Project:** Can the Baby GOAT Surpass the GOAT?  
**Status:** PBP aggregation and 262-game weekly-stat audit passed in the user's local run (reported October 25, 2026). Independent manual checks were conducted for some games; the full external sample is not yet documented.  
**Scope:** First 131 regular-season starts of Tom Brady and Patrick Mahomes (262 player-game records).

## 1. Purpose

Build a per-start rushing and mobility table, independently from the validated passing pipeline. The master table defines **which games the QB started**; play-level IDs define **which rushes and sacks the QB personally incurred**. Backup QB actions must not be attributed to the starter.

## 2. Inputs and Outputs

| Path | Grain | Purpose |
|---|---|---|
| `data/processed/qb_first_131_starts.parquet` | One quarterback start | Sample definition, player ID and team |
| `data/raw/play_by_play/pbp_{season}.parquet` | One PBP event | Source records for attempts, mobility, sacks |
| `data/processed/qb_rushing_plays.parquet` | One credited QB rush | Classified rushing audit trail |
| `data/processed/qb_sack_plays.parquet` | One credited sack on QB | Sack audit trail |
| `data/processed/qb_rushing_stats.parquet` | One quarterback start | Derived game-level metrics; must contain 262 rows |
| `data/processed/qb_rushing_stats.csv` | One quarterback start | Human-readable derived metrics |
| `reports/validation/rushing_game_comparison.csv` | One quarterback start | PBP versus weekly-stat comparison |
| `reports/validation/rushing_discrepancies.csv` | Games with missing/unequal references | Actionable audit findings |
| `reports/validation/rushing_validation_summary.md` | Audit summary | Automated cross-pipeline validation status |

## 3. Metric Definitions

| Output field | Definition | Caveat |
|---|---|---|
| `carries` | Count of credited official-style rushing attempts | Includes scrambles and kneel-downs; validate against weekly player stats |
| `rushing_yards` | Sum of `rushing_yards` credited to player | Negative values are valid |
| `rushing_tds` | Sum of credited rushing touchdowns | Do not include passing touchdowns |
| `scrambles` | QB rushes flagged `qb_scramble == 1`, excluding kneels | Source classification is not a full tactical annotation |
| `scramble_yards` | Yards on flagged scrambles | Part of total rushing yards |
| `designed_runs` | Credited QB rushes that are neither a scramble, an aborted-snap rush, nor a kneel | **Proxy:** not a verified play-call classification |
| `designed_run_yards` | Yards on the above proxy | Subject to classification errors |
| `aborted_rushes` | Credited QB rushing attempts identified as aborted-snap plays | Excluded from designed-run proxy |
| `aborted_rush_yards` | Credited rushing yards on aborted-snap plays | A guarded, auditable one-play 2023 correction is documented separately |
| `kneels` | Credited QB rushes marked as kneel by field, play type, or description | Historical indicators may be inconsistent |
| `kneel_yards` | Yards on kneels | Usually negative |
| `non_kneel_carries` | `carries - kneels` | Better for QB running-usage comparisons |
| `non_kneel_yards` | `rushing_yards - kneel_yards` | Excludes game-management kneel losses |
| `sacks_taken` | Credited sacks on QB | Sack is **not** an official rushing attempt |
| `sack_yards_lost` | Positive magnitude of yardage lost on sacks (`-sum(yards_gained)`) | Compare with **absolute value** of weekly reference |
| `yards_per_carry` | `rushing_yards / carries` | Null when denominator is zero |
| `yards_per_non_kneel_carry` | `non_kneel_yards / non_kneel_carries` | Null when denominator is zero |

**No double counting:** A scramble is part of official rushing yards and may also be a QB dropback in later EPA analysis. Do not sum rushing EPA and dropback EPA naively. Sacks are tracked separately from official rushes.

## 4. Identification and Inclusion Rules

1. Filter PBP to games in the validated 262-row master table and `season_type == REG`.
2. Exclude two-point conversion attempts from regular box-score rushing and sack counts.
3. Require `(game_id, player_id, posteam)` to match `(game_id, player_id, team)` in the master table.
4. Select rushing plays by rushing indicator + play type, or explicit kneel evidence.
5. Identify kneels with `qb_kneel`, `play_type`, and a documented description fallback. Do not guess the QB when the rusher ID is missing: stop and audit.
6. Select sacks with a sack indicator, a pass play type, and the passers' IDs.
7. Do not fill missing yards in **credited** plays with zero. Treat invalid source values as validation failures.
8. Left-join per-game aggregates back onto all 262 starts to preserve zero-carry games.

## 5. Validation Plan

**Level A — Internal structural checks**

- Exactly 262 distinct player-game records; same IDs as the master table.
- Partition check: `carries = scrambles + designed_runs + aborted_rushes + kneels`.
- Yardage partition check: `rushing_yards = scramble_yards + designed_run_yards + aborted_rush_yards + kneel_yards`.
- Non-kneel attempts and yards must equal total rushing attempts and yards minus kneels.
- No duplicate `(game_id, play_id)` in the selected PBP records.
- No suspicious unattributed kneels or sacks on the studied teams without review.
- Impossible counts or missing required yardage block completion.

**Level B — nflverse weekly stats (ALL 262 starts)**

- Match `carries`, `rushing_yards`, `rushing_tds`, `sacks_suffered`, and `abs(sack_yards_lost)` for every QB-game key.
- This is a **cross-pipeline consistency check, not independent source verification**.
- Preserve every mismatch for investigation; never adjust totals to force matching.

**Level C — Independent box-score checks**

- Review a season-stratified subset with NFL or Pro Football Reference game box scores.
- Cover both QBs and early/late starts, including games with scrambles, kneels, sacks and substitution.
- Record URLs, reviewers and checked values in the project's existing external-review records.

## 6. Known Constraints and Research Notes

- Historical PBP may classify kneels inconsistently, so the script includes a conservative textual fallback; audit any mismatch found in weekly totals.
- An unflagged scramble may appear among `designed_runs`. Interpret this field as **non-scramble, non-aborted, non-kneel rushes**, not a ground-truth classification of the play called in the huddle.
- The audited 2020 Chiefs–Saints lateral play requires `td_player_id == player_id` to credit a rushing touchdown to its actual scorer. A play-level `rush_touchdown` flag alone is insufficient.
- The audited 2023 Chiefs–Jaguars aborted snap requires a guarded correction of one QB rushing yard, preserving the raw value and correction reason. See `docs/rushing_discrepancy_report.md` if that report is tracked in this repository.
- The 262-game automated audit passed according to the user's local execution; it remains a same-ecosystem cross-check, not an independent review of every game.
- A starting quarterback can be replaced mid-game. Include the **start** in the study, but never assign the backup's carries or sacks to the starter.
- Fumbles and EPA are **out of scope for this extraction**; they will have their own documented definitions and validation.

## 7. Execution

From the repository root, with the virtual environment active:

```bash
python3 scripts/create_rushing_stats.py
python3 scripts/validate_rushing_stats.py
```

**The user reports that the internal and cross-pipeline checks passed after the documented corrections.** The analysis integration must preserve four rushing categories, including aborted snaps; otherwise an outdated three-category partition check will fail.

## 8. References

- [nflfastR PBP definitions](https://nflfastr.com/reference/fast_scraper.html)
- [nflfastR player statistics dictionary](https://nflfastr.com/articles/stats_variables.html)
- [nflreadpy player statistics loader](https://nflreadpy.nflverse.com/api/load_functions/)
- [nflverse data update schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)
