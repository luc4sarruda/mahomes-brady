# Three-Year Relative QB EPA/Dropback — Research Methodology

## Research purpose

The single-season baseline controls for the NFL dropback environment of a particular season. The three-year (rolling-window) baseline is a **sensitivity analysis**: it tests whether our observed Brady–Mahomes relative EPA comparison changes when short-term league-wide fluctuations are smoothed over adjacent seasons.

This analysis is retrospective and descriptive. It does not model or explain the causal effects of rules, teammates, competition, coaching, or changing offensive schemes.

## Inputs and invariants

- `data/processed/nfl_season_dropback_baselines.parquet`: 20 validated league reference seasons, with finite `qb_epa` sums and usable dropback counts.
- `data/processed/qb_game_era_adjusted.parquet`: 262 study-QB starts, already attributed with the **same corrected dropback definition** used to build the NFL baseline.
- `data/processed/qb_study_season_era_summary.parquet` and `qb_first_131_era_summary.parquet`: previously validated study aggregations used for reconciliation.

This pipeline does not revisit or modify the original PBP, QB passing/rushing totals, per-season baseline, or previously reported percentiles.

## Primary calculation

For study season *s*, let *W(s)* be the permitted set of neighboring NFL seasons (defined below). The window baseline is **dropback-weighted**, using the previously validated league aggregates:

\[
\mu_{W(s)}=\frac{\sum_{t\in W(s)}\sum_{i\in\mathrm{NFL\ DBs}(t)}\mathrm{QB\ EPA}_i}{\sum_{t\in W(s)}N_{t,\mathrm{valid}}}
\]

Each individual QB game is then evaluated against its season's window baseline:

\[
\mathrm{ThreeYearRelativeEPA/DB}_g=\frac{\mathrm{QB\ EPA}_g}{N_g}-\mu_{W(s(g))}
\]

To summarize all 131 starts, **weight by the study quarterback's usable dropbacks**, not by game or season counts:

\[
\mathrm{ThreeYearRelativeEPA/DB}_{131}=\frac{\sum_g[\mathrm{QB\ EPA}_g-N_g\mu_{W(s(g))}]}{\sum_g N_g}
\]

Season-relative EPA/DB is also preserved without modification as the main historical comparison. The three-year statistic tests robustness to a different baseline; it is not a different attribution of a quarterback's plays.

## Explicit window policy

**Never bridge the unobserved 2011–2016 seasons.** The independent study eras are 2001–2010 and 2017–2026.

- **Interior full seasons**: preceding, current, and following **full** regular seasons, e.g. 2007 uses 2006–2008; 2022 uses 2021–2023.
- **Start/end full-season boundaries**: use the two available adjacent full seasons, e.g. 2001 uses 2001–2002; 2010 uses 2009–2010; 2017 uses 2017–2018.
- **2025**: use 2024–2025 only. Because 2026 is partial, it must **not** change the reference for a completed 2025 season.
- **2026 (provisional)**: use the full 2024 and 2025 seasons together with 2026 through the study cutoff of October 18, 2026, weighted by usable NFL dropbacks. This is a **trailing two-full-plus-partial** window, not a symmetric centered window. It is labeled provisional and can change as 2026 progresses.

Thus, despite the metric's convenient name, the windows are not always exactly three *complete* seasons. The window years, type and sample size are carried explicitly on every exported record. The 2026 provisional reference must not be compared to complete-season windows without this qualification.

## Validation

The pipeline must:

1. Preserve 20 league seasons, 262 unique games and exactly 131 starts per QB.
2. Verify the validated annual EPA numerators, denominators, and rates; raise exceptions for any mismatch.
3. Ensure every league window uses distinct, chronologically adjacent seasons within the same study era.
4. Recalculate the three-year league EPA/DB from the sum of NFL QB EPA divided by the sum of *valid* NFL dropbacks, never an average of annual averages.
5. Reconcile game, study-season and 131-start three-year EPA totals under the correct study-QB dropback weights.
6. Reproduce the original annual absolute and season-relative EPA figures without changes.
7. Write outputs only after successful validation.

## Interpretation

- **Annual-relative** is the primary season-specific benchmark; **three-year-relative** is a smoothing robustness comparison.
- Centered windows use the following season for historical comparison, so they must **not** be used as prospective rankings or predictions at the time of the studied season.
- This smoother can obscure an actual abrupt change in NFL offensive efficiency, so agreement is informative but disagreement does not automatically imply an error.
- 2026 remains partial. Intervals at the start and end of eras use special window policies and should be interpreted cautiously.
- The analysis does not establish statistical significance or separate quarterback talent from teammates and opponents.

## Outputs

Run `python3 scripts/build_three_year_relative_epa.py` from the repository root. All generated parquet outputs also have CSV copies.

- `data/processed/nfl_three_year_dropback_baselines.parquet`
- `data/processed/qb_game_three_year_relative.parquet`
- `data/processed/qb_study_season_three_year_summary.parquet`
- `data/processed/qb_first_131_three_year_summary.parquet`
- `reports/validation/three_year_relative_quality_audit.csv`

Visualize the results under the **Three-Year Relative EPA/DB** section of `notebooks/03_era_adjusted_analysis.ipynb`.
