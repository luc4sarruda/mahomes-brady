# Research Protocol — GOAT vs. Baby GOAT

**Editorial title:** *Can the Baby GOAT Surpass the GOAT?*

**Technical title:** *Tom Brady vs. Patrick Mahomes: An Era-Adjusted Analysis of Their First 131 NFL Starts*

**Version:** 1.0 — October 22, 2026  
**Status:** Pre-analysis research protocol; no hypotheses have been tested.  
**Career development objective:** A reproducible data science portfolio project aimed at entry-level roles.

---

## 1. Research Objective

Quantitatively compare the first 131 regular-season NFL starts of Tom Brady and Patrick Mahomes, focusing on (i) individual production, (ii) efficiency relative to their respective eras, (iii) performance evolution over the sample, and (iv) the team context behind their wins. The project will **not** attempt to predict future championships, attribute causal effects to roster changes, or objectively settle the greatest-of-all-time debate.

**Primary research question:**

> How do Tom Brady and Patrick Mahomes compare through their first 131 NFL starts, once individual performance, career evolution, and era differences are considered?

**Historical starting point:** Both quarterbacks reached 100 regular-season wins as starters in 131 starts. Mahomes reached that milestone on October 18, 2026; Brady reached it on October 4, 2010. Independently reproducing these totals is a mandatory step in the data pipeline.

## 2. Study Scope and Constraints

| Dimension | Study rule |
|---|---|
| Players | Tom Brady and Patrick Mahomes |
| Sample | Each quarterback's **first 131 starts**, in chronological order |
| Brady's period | 2001–2010, ending at his 131st start |
| Mahomes's period | 2017–2026, ending at his 131st start |
| Games included | Regular season only (`REG`); exclude playoffs and preseason |
| Primary observation unit | Quarterback × game started |
| Secondary observation units | Offensive play, pass attempt, or dropback, as defined for each metric |
| Comparison population | NFL quarterbacks in each reference season, under documented eligibility rules |
| Analysis frequency | Cumulative by start and across fixed start-number segments; season-based league baselines |
| Data cutoff | **October 18, 2026**, to prevent games after the milestone from entering the sample |
| Out of scope | Forecasting championships; speculating about health; inferring Cover 2 without coverage data; claiming causation without an identification strategy |

**Important:** A sample of 131 starts is **not** equivalent to ten complete seasons. The players missed games at different points in their careers, and all results must state their denominators. Mahomes's first start was in 2017, before his 2018 breakout season. His 2026 season is incomplete at the cutoff; Brady's 2010 season must also be truncated at his 131st start.

## 3. Research Questions and Priorities

### RQ1 — Era-Adjusted Individual Efficiency (REQUIRED)

**Question:** How do the players' efficiency metrics differ across their first 131 starts, both in absolute terms and relative to NFL baselines in the corresponding seasons?

**Metrics:** Passing yards per attempt (Y/A), passing touchdown rate, interception rate, EPA per quarterback dropback, and season-relative EPA per dropback.

**Permissible interpretation:** Differences in **observed performance** under distinct circumstances. Do not automatically attribute every difference to individual talent.

### RQ2 — Performance Evolution Across 131 Starts (REQUIRED)

**Question:** Did each quarterback's performance change between the beginning and end of the sample?

**Method:** Four predefined chronological segments: starts 1–33, 34–66, 67–99, and 100–131. A 16-game rolling average may be used for visualization only. Rolling windows overlap and must not be treated as independent observations.

**Metrics:** Y/A, interception rate, EPA/dropback, and season-relative EPA/dropback.

**Permissible interpretation:** Observed trends and variability. Do not automatically interpret changes as aging effects or tactical adaptations.

### RQ3 — Wins and Team Context (REQUIRED; DESCRIPTIVE)

**Question:** Although both quarterbacks reached a 100–31 record, how did their teams differ in point differential and points allowed during those starts?

**Metrics:** Win percentage, points scored per game, points allowed per game, and average point differential, with changes tracked across the sample.

**Permissible interpretation:** Contextualize team outcomes. These measures cannot isolate the causal contribution of the quarterback, head coach, or defense.

### RQ4 — Supporting Cast and Strategic Adaptation (FUTURE PHASE)

Investigate target concentration, changes in receiving personnel, and documented events. All historical claims about roster changes must be supported by dated external sources. Before-and-after analyses involving Tyreek Hill, Randy Moss, Wes Welker, or coaching changes are **observational comparisons**, not automatically valid natural experiments. Detailed defensive-coverage analysis requires comparable tracking or charting data, which are not uniformly available for the full period.

### RQ5 — Playoffs, Championships, Legacy, and Longevity (FUTURE PHASE)

Handle these topics in a separate chapter. Never merge playoff games into the 131-start regular-season sample. Do not derive precise long-term forecasts from this historical sample alone.

## 4. Pre-Specified Hypotheses and Evaluation Criteria

The following are **pre-specified exploratory hypotheses**, with no assumed winner:

- **H1 — Relative efficiency:** The quarterbacks differ in mean era-relative efficiency, measured as EPA/dropback minus the season-specific league average. Report the magnitude, direction, coverage, and uncertainty of the observed difference. Do not present this observational comparison as a pure test of individual ability.
- **H2 — Career evolution:** Each quarterback's relative efficiency may differ between the early segment (starts 1–33) and the late segment (starts 100–131). Report within-player changes without assuming a direction.
- **H3 — Team context:** The two 100–31 records occurred under potentially different team contexts, as described by points allowed and point differential. Treat the analysis as contextual and descriptive, not causal.

**Decision rule:** A rising or falling line is not sufficient evidence that a hypothesis is confirmed. Present sample sizes, denominators, effect sizes, and, when appropriate, confidence intervals obtained by resampling at the **game level**.

## 5. Data Sources and Source Hierarchy

1. **nflverse / nflreadpy — Schedules and game metadata.** Game IDs, season, game date, `game_type`, `home_qb_id`, `away_qb_id`, and final scores. Identify starters by **player ID**, not by name strings alone.
   - https://nflreadpy.nflverse.com/api/load_functions/
   - https://nflreadr.nflverse.com/articles/dictionary_schedules.html
2. **nflverse / nflreadpy — Play-by-play.** Play-level data available back to 1999, including EPA, pass attempts, passing touchdowns, interceptions, sacks, and related play descriptors. Primary source for efficiency measures.
   - https://nflfastr.com/
   - https://nflfastr.com/reference/field_descriptions.html
3. **Pro Football Reference and official NFL records.** Independent cross-checks for starts, outcomes, and box scores; do not rely on a single record source for milestone validation.
   - https://www.pro-football-reference.com/
4. **Dated reporting and official team/NFL announcements.** Supporting evidence for historical milestones and personnel changes. Record each URL, publication date, and specific claim it supports.

**Known coverage constraints:** nflfastR play-by-play spans the relevant years, but completion probability (CP) and completion percentage over expected (CPOE) are not consistently available before 2006. **CPOE is excluded from the core 131-start comparison**, since much of Brady's early sample lacks it. Detailed defensive-coverage data are likewise not comparable throughout the complete period.

## 6. Core Metric Dictionary

| Metric | Numerator | Denominator | Scope / interpretation |
|---|---|---|---|
| Wins | Team wins in games started by the QB | 131 starts | Starter assigned using game metadata |
| Passing Y/A | Total passing yards | Official pass attempts | Excludes sacks from denominator, as in conventional passing statistics |
| Passing TD% | Passing touchdowns | Pass attempts | Excludes rushing touchdowns |
| INT% | Interceptions thrown | Pass attempts | Do not replace with an interception-per-game rate |
| QB EPA/dropback | Sum of QB-attributed EPA | QB-attributed dropbacks | Include sacks and scrambles as defined by the data dictionary; document ambiguous cases |
| League EPA/dropback | Sum of QB-attributed EPA in the eligible reference population | Corresponding dropbacks | Season-specific baseline; explicitly handle partial-season comparisons |
| Era-relative EPA | QB EPA/dropback minus the season reference EPA/dropback | Not applicable | Compare **differences from contemporary baselines**, not only raw EPA across eras |
| Points allowed/game | Points allowed by the team during the QB's starts | Games in sample | Team measure, not a defense-only measure |
| Point differential/game | Points scored minus points allowed | Games in sample | Influenced by offense, defense, and special teams |

**Implementation note:** For dropback measures, use `qb_dropback` and verify attribution to the appropriate quarterback on pass plays, sacks, and scrambles. **Do not filter only `pass_attempt == 1`.** Confirm the availability and interpretation of `qb_epa` in the downloaded version. For official passing measures, align pass-attempt definitions with box scores and cross-check totals against a second source.

## 7. Data Quality Policy

**All checks must pass before substantive analysis:**

- [ ] Exactly 131 **unique** starts for each quarterback; 262 rows in the combined starts table.
- [ ] Every included game is regular-season (`REG`) and on or before the defined cutoff for the respective player.
- [ ] Each player's starts are sorted chronologically and numbered `start_no` from 1 through 131.
- [ ] The win/loss record reproduces **100–31** for both players; document any ties or other exceptional outcomes if encountered.
- [ ] Player IDs are cross-verified across at least two relevant data tables or identifier systems before play-level filtering.
- [ ] All play-level measures have documented denominators and missing-value handling rules.
- [ ] Aggregate passing statistics are checked against official records for a selection of games and seasons.
- [ ] Report valid-play and valid-game coverage for every metric in both groups. Exclude noncomparable measures from the main analysis rather than imputing missing values as zero.
- [ ] Record the library version, data acquisition date, and exact start/game cutoff used.
- [ ] Never treat the final partial season in either sample as a full season.

**Proposed coverage threshold:** At least 95% of records must be valid for a metric to appear in the primary results. If coverage falls below this threshold, investigate the cause and consider reporting the metric only in an appendix with qualifications. This threshold is a **project choice**, not a universal standard. Also inspect whether missingness differs systematically by era.

## 8. Era-Adjustment Strategy

1. Build a reference dataset of eligible NFL dropbacks in each relevant season, not just plays from New England and Kansas City.
2. Predefine quarterback eligibility criteria if making player rankings (for example, a minimum number of seasonal dropbacks); report sensitivity to that threshold. For a league-wide play-weighted baseline, document whether all qualified offensive dropbacks are included.
3. Estimate league-average EPA per dropback for each season.
4. Compute `relative_epa = qb_epa_per_dropback - league_average_epa_per_dropback_in_same_season` for each quarterback-season segment included in the 131-start sample.
5. Aggregate the season-relative values across the player's sample using the **number of eligible dropbacks** as weights.
6. For Brady's truncated 2010 sample and Mahomes's truncated 2026 sample, document partial-season coverage. Construct league references using information available up to each cutoff and test sensitivity to alternative season baselines where appropriate; do not introduce post-cutoff information into a purported as-of-cutoff analysis.
7. If time permits, estimate uncertainty using a **game-level bootstrap**. Do not resample individual snaps as if they were independent.

**Principle:** Raw totals from the 2000s and 2020s are not directly comparable without considering opportunities, league context, and sample coverage.

## 9. Five Planned Visualizations

1. **Figure 1 — The Road to 100 Wins.** Cumulative wins versus `start_no` (1–131) for both players. Both curves end at 100 wins; the paths may differ.
2. **Figure 2 — Conventional Passing Production.** Compare Y/A, TD%, and INT%, explicitly labeling values and denominators. Use three small charts or a clearly labeled table-chart.
3. **Figure 3 — Era-Adjusted Efficiency.** Player EPA/dropback **minus** the corresponding NFL season baseline, aggregated across the 131 starts.
4. **Figure 4 — Performance Evolution.** Era-relative EPA/dropback over the four start-number segments: 1–33, 34–66, 67–99, and 100–131.
5. **Figure 5 — Team Context.** Points allowed per game and/or point differential within those same four segments.

**Required figure metadata:** Each figure must state its unit, population, source, operational definition, sample size (`N`), central observation, and interpretive limitation.

## 10. Deliverables and Definition of Done

- `research_protocol.md` — This version-controlled protocol and decision history.
- `data_dictionary.md` — Definitions, provenance, filters, and coverage of each field used.
- `notebooks/01_data_validation.ipynb` — Acquisition and validation of the 262 starts.
- `notebooks/02_descriptive_analysis.ipynb` — Descriptive tables and player-level analysis.
- `notebooks/03_era_adjustment.ipynb` — League baselines and comparative figures.
- `data/processed/qb_starts_131.parquet` — Validated 262-row starter table.
- `data/processed/qb_plays_filtered.parquet` — Attributed play-level data with documented filtering rules.
- `reports/figures/` — Five figures exported as SVG or PNG.
- `reports/week1_findings.md` — A concise, up-to-two-page summary with three findings, three limitations, and next steps.
- `README.md` — Research question, approach, reproduction instructions, and provisional findings.

**Week 1 completion standard:** The reproducible pipeline runs from original data; both 131-start samples and 100–31 records are validated; **at least 3 of the 5 planned figures** are produced; and the report includes at least one meaningful era-adjusted comparison. Remaining figures may be completed in a later extension without sacrificing rigor. Do not publish strong cross-era claims without Figure 3 or an equivalent era-adjustment analysis.

## 11. Week 1 Work Plan (12–15 Hours)

| Day | Time | Task | Acceptance criteria |
|---|---:|---|---|
| 1 | 1.5–2 h | Set up repository; read data dictionaries; download schedules and play-by-play | Working environment + data inventory |
| 2 | 2 h | Identify starters and select each player's first 131 starts | 131 + 131 starts and 100 + 100 wins independently validated |
| 3 | 2–2.5 h | Extract and verify passing production | Y/A, TD%, and INT% with explicit denominators |
| 4 | 2–2.5 h | Calculate QB EPA/dropback and seasonal league baselines | Era-adjusted comparison + coverage checks |
| 5 | 2–2.5 h | Build career trajectories and team-context charts | 3–5 charts with careful interpretations |
| 6 | 1.5–2 h | Audit figures, numbers, sources, and limitations | Quality log + defensible provisional findings |
| 7 | 1–1.5 h | Organize README, report, and personal reflection | Reproducible GitHub project + career-reflection notes |

## 12. Required Limitations in the Final Report

- Wins are team outcomes; a starting QB does not produce them independently.
- EPA is model-derived and depends on dataset construction. **QB EPA is not an isolated measure of individual ability.**
- Era adjustment reduces, but does not remove, differences in rules, opponents, teammates, and strategic approaches.
- The two samples come from different NFL eras; structural differences in schedule length and context remain.
- Games, plays, and observations across a time series are not completely independent.
- Ending each sample at the 100th win is a deliberate endpoint choice. It cannot evaluate full-career longevity, ultimate legacy, or future performance.
- The lack of uniform historical coverage data prevents detailed claims about particular defensive coverages across the entire study window.

## 13. Repository Structure

```text
brady-vs-mahomes/
├── README.md
├── research_protocol.md
├── data_dictionary.md
├── requirements.txt
├── data/
│   ├── raw/                 # Do not commit restricted or large raw datasets
│   └── processed/
├── notebooks/
│   ├── 01_data_validation.ipynb
│   ├── 02_descriptive_analysis.ipynb
│   └── 03_era_adjustment.ipynb
├── src/
│   ├── acquire.py
│   ├── construct_starts.py
│   └── metrics.py
└── reports/
    ├── figures/
    └── week1_findings.md
```

## 14. Research Decision Log

| Date | Decision | Rationale | Consequence |
|---|---|---|---|
| Oct 22, 2026 | First 131 starts; regular season only | Identical number of starts at the 100-win milestone | Playoffs excluded from the primary sample |
| Oct 22, 2026 | Use season-specific league-adjusted EPA | Reduces cross-era distortion | Requires a league-wide reference dataset |
| Oct 22, 2026 | Exclude CPOE from the primary results | Incomplete pre-2006 availability for Brady | May be used in a clearly limited appendix |
| To be determined | QB eligibility rule for league comparisons | Avoid arbitrary or biased peer-group selection | Run sensitivity checks |

## 15. Initial Reference Sources

- New England Patriots — Tom Brady biography and 100th win in his 131st start: https://www.patriots.com/news/tom-brady-bio
- NBC Sports, October 19, 2026 — Mahomes matches Brady's 100 wins in 131 starts: https://www.nbcsports.com/nfl/profootballtalk/rumor-mill/news/patrick-mahomes-ties-tom-brady-for-fewest-games-to-100-qb-wins
- nflreadpy — Data loading functions: https://nflreadpy.nflverse.com/api/load_functions/
- nflfastR — Historical coverage since 1999; CP/CPOE availability from 2006: https://nflfastr.com/
- nflfastR — Beginner's guide and QB EPA documentation: https://nflfastr.com/articles/beginners_guide
- nflreadr — Schedule schema and quarterback starter fields: https://nflreadr.nflverse.com/articles/dictionary_schedules.html

---

## Personal Career Reflection (Complete After Week 1)

Rate each item from 1 to 5: (1) enjoyment of investigative work; (2) willingness to audit inconsistent data; (3) interest in statistics and metric definitions; (4) enjoyment of communicating findings; and (5) desire to repeat a similar analysis on another topic.

**Guiding principle:** This project's value lies in learning to produce **verifiable, reproducible conclusions**. The sports narrative should attract readers, never determine the research outcome.
