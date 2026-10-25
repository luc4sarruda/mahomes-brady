# Data Quality Log

**Project:** Can the Baby GOAT Surpass the GOAT?  
**Dataset:** Brady vs. Mahomes — First 131 Regular-Season Starts  
**Document status:** Active  
**Last updated:** October 25, 2026

## Purpose

This document records data quality issues discovered during acquisition, validation, and analysis. Each issue must include the affected records, observed problem, supporting evidence, resolution, and potential impact on the research.

Raw datasets must remain unchanged. Corrections belong in documented processing logic, and all analytical outputs must be reproducible from the original sources.

## Quality Checks

| Check ID | Validation | Expected result | Current status |
|---|---|---|---|
| QC-001 | Unique `game_id` values in the regular-season schedule data | No duplicate games | Passed in master-table pipeline |
| QC-002 | First starts of Tom Brady and Patrick Mahomes | September 30, 2001; December 31, 2017 | Passed |
| QC-003 | Number of regular-season starts per quarterback | 131 each (262 total) | Passed |
| QC-004 | Starting record through start 131 | 100 wins, 31 losses, 0 ties per player | Passed |
| QC-005 | Date of each 131st start | Brady: October 4, 2010; Mahomes: October 18, 2026 | Passed |
| QC-006 | Unique `(player_id, game_id)` pairs in master table | 262 unique pairs | Passed |
| QC-007 | No null values in required master-table fields | Zero null values | Passed |
| QC-008 | Play-by-play `game_id` references for the 2018 regular season | Zero unmatched PBP records | Passed (45,120 PBP records; 256 games) |
| QC-009 | Historical coverage of all metrics used in comparisons | Coverage documented by player and season | Pending — later analysis |
| QC-010 | Passing totals spot-checked against reported NFL records | Brady 2005 Week 17 and Mahomes 2018 season totals | Passed in local script (limited coverage) |
| QC-011 | All 262 player-game passing records cross-checked against weekly player stats | Exact agreement on five integer metrics, or investigated differences | Passed — user-reported local run; zero unexplained discrepancies |
| QC-012 | NFL/PFR box-score sample across all 20 player-seasons | Exact match, evidence URLs recorded | Partially completed — user-reported sampled external checks passed; sample size and URLs not supplied |

**Scope note:** “Passed” reflects the user's local pipeline output and reported checks, not an independent rerun of their files. Further validation is required before making substantive performance claims.

---

## DQ-001 — Incorrect Starting Quarterback Attribution

| Field | Value |
|---|---|
| **Status** | Resolved for master-table construction; original source preserved |
| **Severity** | High |
| **Affected source** | nflverse schedules |
| **Game ID** | `2005_17_MIA_NE` |
| **NFL season / week** | 2005 / Week 17 |
| **Game date** | January 1, 2006 |
| **Matchup** | Miami Dolphins at New England Patriots |
| **Original `home_qb_name`** | Matt Cassel |
| **Original `home_qb_id`** | `00-0023662` |
| **Verified starter** | Tom Brady |
| **Correct `player_id` in derived master table** | `00-0019596` |

### Description

The nflverse schedules record for `2005_17_MIA_NE` identifies **Matt Cassel** as New England's starting quarterback. However, **Tom Brady started the game**, and Cassel replaced him during the game. Starting credit must be assigned to Brady even though Cassel participated in the game.

### Detection

The initial master-table script selected starts by GSIS player ID only. As a result, the affected Brady start was excluded. Selecting the next recorded start produced an incorrect endpoint and record:

| Measure | Before correction | After correction |
|---|---|---|
| Brady's 131st start | October 17, 2010 | October 4, 2010 |
| Wins | 101 | 100 |
| Losses | 30 | 31 |
| Number of starts | 131 | 131 |

A season-by-season audit of Brady's early starts isolated the discrepancy to the game above.

### Resolution

The processing script applies **one explicit, game-specific exception** while constructing the derived starts table:

1. Match `game_id == "2005_17_MIA_NE"` and the **home** starting quarterback entry.
2. Set the derived `player_id` to Tom Brady's GSIS ID (`00-0019596`).
3. Retain the source QB ID and name for audit purposes.
4. Leave the original schedules Parquet file unchanged.
5. Recompute starts chronologically and validate both players' 100–31 records at start 131.

The exception must **not** be applied to play-by-play passing statistics: Cassel's passes remain attributed to Cassel, and Brady's to Brady. A game start, a passing attempt, and a QB dropback are distinct units of analysis.

### Verification

The user's successful local run reported:

```text
Tom Brady: (100, 31, 0), first=2001-09-30, 131st=2010-10-04
Patrick Mahomes: (100, 31, 0), first=2017-12-31, 131st=2026-10-18
VALIDATED: 262 rows, 16 columns. Master table exported.
```

### Supporting References

- [NFL / New England Patriots — Brady historical records](https://www.patriots.com/)
- [Pro Football Reference — Tom Brady player records](https://www.pro-football-reference.com/players/B/BradTo00.htm)
- [Pro Football Reference — 2005 Patriots schedule and results](https://www.pro-football-reference.com/teams/nwe/2005.htm)
- Local audit output: `data/processed/starter_attribution_audit.csv` (if generated by the current pipeline).

**Evidence follow-up:** Before publication, record permanent page URLs or relevant box-score links explicitly confirming the Week 17 starter and the in-game substitution. The links above are reference entry points, not a substitute for that game-level citation.

### Preventive Action

Keep automated assertions for the number of starts, uniqueness, dates, and win-loss totals. When future schedule updates are downloaded, rerun the audit; remove this exception only if the source record has been corrected and the resulting table passes all validations.

---

## DQ-002 — Play-by-Play Game-Key Integrity (2018)

| Field | Value |
|---|---|
| **Status** | Closed — validation passed |
| **Severity** | Informational |
| **Affected tables** | Schedules and PBP, 2018 regular season |

### Check

A left anti-join from 2018 regular-season PBP records to the regular-season schedule table on `game_id` produced **zero unmatched PBP records**.

```text
Regular-season games: 256
Regular-season play records: 45120
Unmatched play records: 0
```

### Interpretation

This confirms key coverage for the tested 2018 subset. It does **not** by itself validate player attribution, play-level metric definitions, or every other season. Those checks remain separate.

---

---

## DQ-003 — Missing Spike in Passing Attempt Count (2018 Mahomes)

| Field | Value |
|---|---|
| **Status** | Resolved in extraction logic; cross-pipeline audit passed (user-reported) |
| **Severity** | Medium — metric definition |
| **Affected metric** | `attempts`, and derived completion/TD/INT rates and yards/attempt |
| **Affected test** | Mahomes, 2018 regular season |
| **Detection** | Independent historical total expected 580 attempts; first PBP aggregation produced 579 |

### Detection

The original `create_player_stats.py` omitted clock-stopping quarterback spike plays, yielding 579 attempts instead of 580. Completions (383), passing yards (5,097), touchdowns (50), and interceptions (12) matched the official 2018 Mahomes season totals.

### Resolution

The passing-attempt selection logic includes `play_type == 'qb_spike'` and `qb_spike == 1` as incomplete official pass attempts. Sacks, scrambles, and two-point tries remain excluded from official passing attempts. Original PBP files are unchanged.

### Local Verification

The user reported that the corrected script passed both existing historical reference checks and exported its derived tables. The exact spike `game_id`/`play_id` still needs to be recorded. The user subsequently reported that the full 262-game cross-pipeline audit passed; this is a shared-ecosystem consistency check, not independent verification of all 262 games.

### Follow-up

- [ ] Record the affected spike's `game_id` and `play_id`.
- [x] Run the 262-game comparison with nflverse weekly player statistics (user-reported pass).
- [ ] Complete and record the season-stratified NFL/PFR box-score sample; some manual checks were reported as passing, but their count and URLs are not yet recorded.

---

## DQ-004 — Comprehensive Game-Level Passing Statistics Audit

| Field | Value |
|---|---|
| **Status** | Cross-pipeline audit passed (user-reported); external sample partially verified |
| **Severity** | High for conclusions based on passing statistics |
| **Scope** | 262 starts × 5 integer metrics = 1,310 comparisons |

**Execution update (user-reported, October 25, 2026):** `scripts/validate_passing_stats.py` completed with 100% agreement, and a subset of games was manually checked without discrepancies. The number and identities of manual checks, their direct source URLs, the exact audit summary, and checksums have not been provided here. No independent rerun of the user’s local files was performed. The weekly stats share source provenance with PBP, so agreement is a cross-pipeline consistency check rather than independent confirmation of every NFL box score.

**Evidence:** See `docs/passing_statistics_validation.md`. Results and URLs must be added after the checks actually run.

## Open Validation Work

- [ ] Run the PBP-to-schedules anti-join across **all** study seasons.
- [ ] Measure missingness and field availability for each passing-efficiency metric by season and quarterback.
- [x] Compare all 262 starts across five passing metrics to weekly nflverse player stats (user-reported full pass).
- [ ] Record full season-stratified NFL/PFR box-score coverage and direct links; several manual checks reportedly passed.
- [ ] Verify that `qb_dropback` correctly captures sacks and scrambles and that QB attribution is consistent.
- [ ] Document source versions, extraction timestamps, and reproducible checksums for analysis snapshots.
- [ ] Save exact game-level evidence links for DQ-001.

## New Issue Template

```markdown
## DQ-XXX — Short Issue Title

- **Status:** Open / Investigating / Resolved / Accepted limitation
- **Severity:** Low / Medium / High / Critical
- **Affected dataset(s):**
- **Affected games / seasons / players:**
- **Detection date:**

### Description
What was observed, and why is it a data quality problem?

### Detection
Which query, test, or independent source revealed it?

### Resolution
What was changed in the derived data or processing logic?
Were raw files preserved?

### Verification
Which independent checks passed after the correction?

### Impact on Findings
Which metrics, samples, or visualizations could be affected?

### References
Provide direct links and/or reproducible queries.
```
