# Passing Statistics Validation Summary

- **Generated (UTC):** 2026-10-25T18:42:52.663099+00:00
- **Scope:** First 131 starts for each of two players; 262 player-game rows
- **Seasons represented:** 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026
- **nflreadpy version:** 0.1.5
- **Polars version:** 2.0.0
- **Rows matching nflverse weekly stats:** 262
- **Rows with mismatched stats:** 0
- **Rows with missing reference statistics:** 0
- **Planned independent NFL/PFR review rows:** 21

## Interpretation

These comparisons check agreement between a custom play-by-play aggregation and
nflverse weekly player statistics, using player ID and game ID. **They are not
independent verification of the underlying source**, because both products belong
to the nflverse data ecosystem. A complete review requires an external NFL/PFR
box-score sample, recorded in `official_boxscore_review_template.csv`.

## Metric Definitions

- Passing attempts: NFL-style official attempts, including spikes.
- Completed passes: passes completed and credited to the QB.
- Passing yards: passing yards credited to the QB.
- Passing TDs: passing touchdowns credited to the QB.
- Interceptions: passes intercepted while attributed to that QB.

## Files

- `passing_game_comparison.csv`: all player-game comparisons
- `passing_discrepancies.csv`: only unmatched or differing rows
- `official_boxscore_review_template.csv`: seeded, season-stratified external review

## Validation State

**INCOMPLETE** — External box-score review is pending.
