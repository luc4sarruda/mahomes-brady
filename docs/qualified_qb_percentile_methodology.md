# Qualified QB EPA/Dropback Percentiles — Methodology

## Research purpose

Estimate where Tom Brady and Patrick Mahomes ranked among other **qualified NFL quarterbacks in the same season**, rather than comparing only against the average of all league dropbacks. This analysis complements (but does not replace) league-relative EPA/dropback.

## Population and dropback definition

- NFL regular-season plays from the study seasons: 2001–2010 and 2017–2026.
- A corrected dropback is `qb_dropback == 1` **OR** (`play_type == "run"` and `qb_scramble == 1`), excluding spikes, kneels, and two-point attempts.
- Historical scramble recovery is identical to `build_nfl_epa_baselines.py`. One play can count only once.
- QB identity uses the same resolved ID as the previous league and study EPA pipelines.
- Only finite `qb_epa` observations enter the EPA numerator and denominator. The single previously audited missing EPA play in 2019 remains excluded, not zero-imputed.
- 2026 data stop on **October 18, 2026** (the study's final game date). No later games are considered.

**Important:** This is *quarterback-attributed EPA*, not pure passing EPA or a causal measure of individual player ability. Sacks and scrambles contribute to the dropback population. The complete-season QB totals can include relief appearances and other starts outside the study's 131-start window.

## Qualification and sensitivity

- **Primary full-season minimum:** at least **200 usable quarterback dropbacks**.
- **Partial 2026 minimum:** `ceil(200 × available league games / 272)`, evaluated using the exact league-game count through the study cutoff. With 92 games, this is **68 dropbacks**.
- Additional sensitivity populations use full-season cutoffs of **150 and 250** usable dropbacks (also prorated in 2026).
- This is a **study-defined analytical threshold**, not the NFL's official passer-rating qualification rule and not a universal or source-prescribed standard. Qualification is based on usable EPA dropbacks, not pass attempts.
- Every season's denominator is the number of qualified **players**, not the number of plays. A QB's season EPA/DB is computed from that QB's own play-level dropbacks.

Qualification changes the league comparison population. This should be tested by reviewing the 150/200/250 sensitivity file before drawing strong conclusions from small percentile differences.

## Percentile definition

Qualified QBs are ordered by their mean `qb_epa` per **usable** dropback in the season. The best is rank 1. With `N` qualified QBs, define:

`Qualified QB Percentile = 100 × (N − descending_midrank) / (N − 1)`

Ties share the average of their ordinal rank positions. Thus the lowest-ranked qualified QB has 0, the highest has 100, and higher percentiles indicate higher measured efficiency **relative to qualified QBs**, not relative to the league's individual plays.

Example: among 30 qualified QBs, a QB ranked 4th (with no ties) has `100 × (30 − 4)/29 = 89.7` percentile. This is a ranking description, **not** a confidence probability and **not** a normal-distribution z-score.

## Scope alignment with the 131-start study

The `nfl_qualified_qb_season_epa` table ranks **full-season QB production** (or games through the partial 2026 cutoff). The `qb_study_season_era_summary` table summarizes **only starts inside the first 131 career starts**. These are not automatically the same sample.

For each research QB season, the pipeline compares:

1. Number of usable QB dropbacks in the full-season distribution versus the selected study starts.
2. Total QB EPA in each sample (tolerance 1e-6).

When both match, the resulting percentile is copied into `study_aligned_qualified_percentile`; otherwise it is **null**, while `qualified_qb_percentile` remains available only as an explicitly labeled *full-season* context statistic. If the QB fails qualification, both percentiles are null and the status is `NOT_QUALIFIED`.

This protects against two distinct pitfalls:
- **Brady in 2010:** only four starts are within the study, but the full 2010 QB season contains games outside the window; the full-season percentile must not be described as the percentile for those four starts.
- **Brady in 2008 / Mahomes in 2017:** a single study start does not automatically make a QB qualified for a seasonal ranking.

Other non-study QB appearances, such as relief plays, may cause additional scope mismatches. These are not errors: they are reasons to keep the two analyses distinct.

## Outputs

| File | Content |
|:--|:--|
| `data/processed/nfl_qb_season_epa_all.parquet` | All QB-season EPA results, including unqualified QBs |
| `data/processed/nfl_qualified_qb_season_epa.parquet` | Qualified league QB distribution, EPA, rank, percentile |
| `data/processed/study_qb_qualified_percentiles.parquet` | 20 research-QB seasons, full-season ranking, study alignment flag |
| `reports/validation/qualified_qb_threshold_sensitivity.csv` | Ranking distributions for 150/200/250 cutoff variants |
| `reports/validation/qualified_qb_percentiles_audit.csv` | League totals and season-by-season reconciliation checks |
| `reports/figures/09_qualified_qb_season_distributions.png` | Season-specific QB distributions |
| `reports/figures/10_qualified_qb_percentiles.png` | QB percentiles across study years, with scope indicators |

CSV versions of the three processed league/study tables are also exported.

## Quality gates

- All 20 league populations match the validated league baselines, including EPA sum and dropback totals.
- Every corrected eligible dropback belongs to one QB; QB identities and `(game_id, play_id)` uniqueness are checked by the shared baseline validator.
- Every qualified QB has at least the defined season-specific minimum usable dropbacks.
- All calculated percentiles lie between 0 and 100.
- No study season is missing its QB in the full-league table.
- Study-aligned percentiles require exact sample alignment, and no full-season percentile is silently substituted for a missing study-aligned value.

## Interpretive limitations

- Percentiles describe *observed rank among an eligibility-filtered peer group*, not a causal QB talent ranking.
- A rank can change when qualification cutoffs change or when EPA varies slightly around a neighboring QB.
- The 2026 peer group is necessarily provisional because it uses a partial NFL schedule and a prorated qualification threshold.
- A full-season ranking for a QB can include non-started games or games beyond the 131-start research window.
- Rankings are cross-season **descriptive** comparisons, not independent samples and not hypothesis tests. To compare the players' 131-start performance directly, retain the dropback-weighted league-relative EPA analysis as the primary measure.
