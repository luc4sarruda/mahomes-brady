# Era-Adjusted Quarterback Performance — Final Research Report

*Can the Baby GOAT Surpass the GOAT? | Notebook 03 | First 131 regular-season starts*

## Executive Summary

This study compares Tom Brady and Patrick Mahomes over their first **131 NFL regular-season starts**, a deliberately matched career window in which both finished **100–31**. It asks a narrower question than who is the greatest quarterback: **which player generated more observed quarterback-attributed EPA per eligible dropback, relative to the NFL environments in which he played?**

**Primary finding:** Mahomes led on both absolute and season-relative efficiency. His observed absolute advantage was approximately **+0.073 QB EPA/dropback**; the difference narrowed to **+0.0381 EPA/dropback** after adjustment for season-specific league baselines. A three-year, dropback-weighted league reference produced a similar, slightly larger gap of **+0.0419 EPA/dropback**. Thus, **the direction of the observed difference is stable under the two league-reference definitions tested**, while its magnitude is considerably smaller than the unadjusted comparison.

The analysis also identifies contrasting career patterns: Mahomes entered his starting career with exceptionally high relative efficiency, while Brady's performance strengthened over time and culminated in an exceptional **2007** peak. These are descriptive findings about the selected games, **not estimates of QB-only causal impact, proof of statistical significance, or predictions of future performance**.

## 1. Research Design and Measurement

- **Sample:** 131 regular-season starts for each quarterback (262 QB-game records), excluding playoffs. In the EPA analysis, Brady contributes **4,607 usable eligible dropbacks** and Mahomes **5,381**.
- **Primary measure:** quarterback-attributed EPA (`qb_epa`) per eligible dropback, including passes, sacks, and tagged scrambles. Spikes, kneel-downs, and two-point attempts are excluded under the validated processing rules.
- **Annual reference:** the NFL's season-specific **dropback-weighted** mean QB EPA, calculated from the league's regular-season plays. The player's 131-start performance is aggregated by usable dropbacks rather than by taking an unweighted average of game rates.
- **Three-year reference:** the dropback-weighted NFL mean in a centered three-season window, with explicitly documented exceptions at study-era boundaries. This is a **smoothing sensitivity analysis**, not a replacement for the primary season-relative measure.
- **Peer ranking:** each player's **full-season** QB EPA/dropback percentile against qualified quarterbacks, with a minimum of 200 eligible dropbacks in the main specification. The qualification rule was also tested at 150 and 250 dropbacks.
- **Scope caveat:** the percentile comparison does not always cover exactly the same games as the 131-start comparison. The **2026 reference is partial through October 18, 2026**.

The following estimates are descriptive and conditional on the selected starts and the EPA model; differences in scheme, supporting cast, opposition and game situations remain present.

## 2. Headline Results — First 131 Starts

| Measure | Tom Brady | Patrick Mahomes | Mahomes − Brady |
|:--|--:|--:|--:|
| Usable dropbacks | 4,607 | 5,381 | — |
| Absolute QB EPA/dropback | ≈ +0.176 | ≈ +0.249 | ≈ **+0.073** |
| Era-matched NFL reference | ≈ +0.022 | ≈ +0.056 | — |
| **Annual-relative QB EPA/dropback** | **+0.1542** | **+0.1923** | **+0.0381** |
| **Three-year-relative QB EPA/dropback** | **+0.1526** | **+0.1945** | **+0.0419** |
| Change when using three-year reference | −0.0016 | +0.0022 | +0.0038 in the gap |

*The absolute and era-matched reference values are rounded from Figure 2; the annual- and three-year-relative values reproduce the four-decimal outputs supplied by the processing script. The last decimal of derived differences can change slightly if full-precision values are used.*

The season adjustment reduces the **observed absolute gap** from about +0.073 to +0.0381 EPA/dropback—approximately a **48% reduction in the descriptive difference**. This **does not mean** that historical era differences *caused* 48% of the original gap. The subtraction merely changes the reference against which each quarterback is evaluated.

For scale, the annual-relative gap equals about **3.81 expected points per 100 eligible dropbacks**; the smoothed-reference gap equals **4.19 per 100**. These are standardized exposure-rate differences, **not predicted scoring margins or expected additional wins**.

## 3. NFL Environment and Annual Relative Performance (Figures 1–3)

**League efficiency varied substantially within both eras**, rather than following a strictly increasing historical trend. For example, the NFL baseline was approximately **−0.0053** EPA/dropback in 2003, **+0.0312** in 2007, **+0.0740** in 2018, **+0.0938** in 2020, and **+0.0159** in 2023. Several Mahomes-era seasons were more efficient on average, but some were below Brady-era seasons. This variation justifies using **season-matched** rather than purely chronological assumptions about the passing environment.

Across the first 131 starts, **both QBs were well above their own era-matched NFL average**, with Mahomes retaining the larger relative aggregate. Their **season profiles**, however, were not uniform:

- **Brady's 2007 performance** exceeded the NFL baseline by approximately **+0.40 EPA/dropback**, the largest relative season segment visible for either player. His early seasons were more modest, while 2004–2007 and 2009 showed stronger relative performance. His negative 2008 bar covers **one study start**, so it is not evidence of a sustained season-long decline.
- **Mahomes showed particularly strong relative production in 2018–2022**, including peaks around **+0.30** in 2018 and **+0.28** in 2022. The subsequent 2023–2026 study segments were less elevated, but remained **above the league baseline** in the displayed sample. The 2017 segment includes **one start**; 2026 includes **five**.

Because these figures use only the starts in the research sample, a partial-season study segment should not be interpreted as the player's entire actual season. No causal attribution to receivers, coaching or defensive strategy can be made from these plots alone.

## 4. Career Evolution and Season Standardization (Figures 4–5)

The **cumulative, dropback-weighted relative EPA** trajectories reveal different shapes. Mahomes accumulated a large positive relative advantage early; as additional games were added, his cumulative average decreased but remained ahead at start 131. Brady began nearer the league reference and progressively increased his cumulative relative performance, particularly through his later study starts.

The **trailing 16-start** chart isolates shorter stretches of form. Mahomes's early and intermediate windows were highly productive, followed by weaker windows later in the comparison and some recovery. Brady's later windows—including the period associated with his 2007 peak—were substantially stronger than his earliest windows. Importantly, consecutive 16-start estimates share most of their underlying games: the curves are **not independent observations**, and apparent trends should not be treated as formal change-point or decline tests.

Season-standardized EPA divides season-relative QB EPA/dropback by the **NFL's play-level standard deviation of QB EPA** for that year. The visual pattern broadly resembles annual-relative EPA: Brady's **2007** season stands out, and Mahomes shows exceptional early-season segments. This is an **effect expressed in play-level dispersion units**, **not** a z-score over the distribution of quarterback means, a QB percentile, or evidence of statistical significance. The notebook also calculates relative positive-EPA play rates as a secondary check; numerical conclusions about that measure should come from its displayed table rather than from EPA-rate plots alone.

## 5. Qualified-Quarterback Peer Distributions (Figures 6–7)

Unlike the play-weighted league average, a qualified-QB percentile compares the **season-level efficiency of individual quarterbacks**. It answers the ranking question: *what fraction of the qualified QB cohort did this player outperform by QB EPA/dropback?*

| Brady study-era season | Percentile | Mahomes study-era season | Percentile |
|:--|--:|:--|--:|
| 2001 | 56.7%† | 2017 | N/Q |
| 2002 | 42.9% | 2018 | **100.0%** |
| 2003 | 67.6% | 2019 | 97.0% |
| 2004 | 82.9% | 2020 | 97.1% |
| 2005 | 88.9% | 2021 | 97.1% |
| 2006 | 86.1% | 2022 | **100.0%** |
| 2007 | **100.0%** | 2023 | 86.8% |
| 2008 | N/Q | 2024 | 76.9% |
| 2009 | 87.9% | 2025 | 78.4% |
| 2010 | **100.0%†** | 2026 | 70.6%‡ |

*Values are rounded to one decimal for readability. N/Q means that the player did not satisfy the specified minimum. † Full-season rankings include QB plays outside the selected starts (notably Brady in 2001 and 2010). ‡ 2026 is provisional and based on the truncated league period.*

Brady's peer ranking progressed from the middle or lower-middle of the qualified distribution in his earliest seasons to the **top-ranked qualified position in 2007**. Mahomes was top-ranked in **2018 and 2022** and near the top through 2021, although his percentile declined in 2023–2026. A lower percentile does **not** mean below-average absolute EPA, nor does a percentile of 100 imply perfect performance or a fixed magnitude of superiority over second place.

**Sensitivity to the qualification threshold.** Recomputing percentiles with minimums of **150, 200 and 250** dropbacks yielded a mean within-season range of approximately **3.9 percentage points for Brady** and **1.5 points for Mahomes** across their nine qualified seasons. Brady's largest range was **11.3 pp in 2002**; Mahomes's was **4.3 pp in 2023**. The top placements for **Brady 2007** and **Mahomes 2018 and 2022** remained at **100.0%** under all three thresholds. Hence the headline peer-ranking patterns are reasonably robust to these *specific* qualification choices, though the threshold affects some early Brady years more strongly.

## 6. Three-Year NFL Baselines — What Changed? (Figures 8–10)

### Figure 8 — Annual vs Three-Year League Environment

The smoothed NFL reference is **less volatile** than a single-year baseline. That is the intended behavior of averaging adjacent seasons; it should **not** be interpreted as evidence that league efficiency itself was stable.

Examples from the computed baselines:

| NFL season | Annual baseline | Three-year reference | What changes? |
|:--|--:|--:|:--|
| 2003 | −0.0053 | +0.0223 | A low annual baseline is pulled upward by neighboring years. |
| 2004 | +0.0438 | +0.0204 | A comparatively strong annual baseline is pulled downward. |
| 2018 | +0.0740 | +0.0520 | The smoothed reference is less demanding. |
| 2020 | +0.0938 | +0.0689 | A particularly high annual league baseline is softened. |
| 2023 | +0.0159 | +0.0385 | A low annual baseline is pulled upward. |
| 2026‡ | +0.0702 | +0.0625 | Provisional reference mixes 2024–2025 with part of 2026. |

*‡ 2026 is partial through October 18, 2026. Values rounded to four decimals.*

The comparison does **not** join the disconnected study eras (2010 and 2017). Most windows use the previous, current and next seasons weighted by their NFL dropback counts. At the edges, **2001, 2010, 2017 and 2025 use two full seasons**; **2026 uses 2024 and 2025 plus the observed partial 2026 season**. These exceptions mean this is not a literal three-*complete*-season reference for every row. Centered windows use future-season information and are appropriate only for **retrospective description**, not real-time forecasting.

### Figure 9 — Season-Level Effects of Changing the Baseline

In this comparison, the quarterback's EPA numerator and sample do **not** change. Only the **league reference subtracted** from it changes. Consequently, when the smoothed league baseline is *lower* than the annual baseline, the QB's relative EPA rises; when it is *higher*, relative EPA falls.

- **Brady:** in **2003**, replacing the unusually low annual baseline with a higher three-year reference reduces his relative EPA. In **2004**, replacing a higher annual baseline with a lower smoothed reference increases it. His standout **2007** season remains exceptional under both calculations. The 2008 and 2010 segments contain only **one** and **four** selected starts, respectively.
- **Mahomes:** **2018 and 2020** look somewhat better relative to the smoothed reference because those years' annual league baselines were higher than their windows. In **2023**, the opposite happens: the higher smoothed baseline reduces his estimated relative advantage. His **2022** peak remains strong under both measures. The 2026 bar is provisional and covers **five** study starts.

These shifts show why a one-year comparison may emphasize a particularly favorable or unfavorable *league-wide* season. They do **not**, by themselves, show changes in quarterback skill.

### Figure 10 — The Aggregate 131-Start Answer

With the **annual** baseline, the observed Mahomes–Brady gap is **+0.0381 EPA/dropback**. With the **three-year** reference, the gap is **+0.0419**. This is a change of **+0.0038 EPA/dropback** (about **10% relative to the annual-gap magnitude**), and **the ranking does not reverse**.

Brady moves from **+0.1542** to **+0.1526**, while Mahomes moves from **+0.1923** to **+0.1945**. The overall finding therefore appears **not highly sensitive to these two particular baseline windows**. This is evidence of *reference-definition robustness*, not a test of statistical significance and not an independent replication of QB EPA.

## 7. Main Findings and Strength of Evidence

1. **Observed advantage:** Mahomes produced higher absolute and era-relative QB EPA/dropback across the selected 131 starts; the annual-adjusted advantage was about **+0.0381 EPA/dropback**.
2. **Era adjustment matters:** subtracting season-specific NFL baselines reduced the observed gap by approximately **48%** compared with the rounded absolute difference.
3. **Reference smoothing does not overturn the result:** the three-year window gave Mahomes a **+0.0419** advantage, close to the annual estimate.
4. **Different trajectories:** Mahomes's early starting years were unusually efficient; Brady's relative efficiency improved across his early starts and peaked sharply in **2007**. The relative EPA curves are descriptive time-series summaries, not causal trend estimates.
5. **Peer-group evidence is consistent with those patterns:** Brady was top-ranked among qualified QBs in **2007**; Mahomes was top-ranked in **2018 and 2022**. These positions remained top-ranked under all three tested minimum-volume thresholds.
6. **A QB's season percentile and EPA relative to the league are not interchangeable:** percentiles capture order among qualifying players; EPA gaps capture a magnitude relative to a *play-weighted* league reference.

## 8. Limitations and Threats to Interpretation

- **Observational, not QB-only causal:** QB EPA retains effects from receivers, offensive line, coaching, opponent defenses, game situations and EPA-model conventions. The study does not isolate individual quarterback talent.
- **No formal uncertainty assessment:** no game-level clustered or season-aware bootstrap intervals or hypothesis tests have yet been reported. A positive observed gap must not be presented as statistically significant.
- **Selected endpoints:** choosing both samples because they reached **100 wins in 131 starts** conditions on a team outcome. The comparison excludes playoffs and may omit useful performance information outside that window.
- **Exposure differs:** Brady and Mahomes contributed **4,607** and **5,381** usable dropbacks, respectively. Per-dropback comparisons adjust for exposure in the denominator, but not for differing opponents or game contexts.
- **Incomplete/unequal seasons:** the study's season bars may contain few starts (Brady 2008: 1; Brady 2010: 4; Mahomes 2017: 1; Mahomes 2026: 5). Full-season peer rankings can include QB plays outside those selected starts; 2026 has an incomplete NFL reference.
- **Historical play classification:** historically tagged scrambles missing the original dropback flag were restored for the EPA definition; untagged QB runs were *not* automatically classified as scrambles. Historical classification choices remain a source dependency.
- **Known missing observation:** one eligible 2019 play (`2019_01_PIT_NE`, play 4166) had missing QB EPA and was excluded from the corresponding league EPA denominator rather than imputed as zero.
- **Reference construction:** the league mean includes the study QBs' own plays, is weighted by dropbacks (not equally by quarterbacks), and is not an opponent-adjusted or qualified-QB-only baseline.
- **Window design:** centered three-year means incorporate adjacent years, including future years, and have unequal edge-year scopes. The partial 2026 observation may change with additional games. Smoothing cannot remove underlying team context or establish a causal era effect.
- **Standardized score interpretation:** dividing by the standard deviation of individual NFL plays is not a percentile among QBs or a standard error of the quarterback's mean.

## 9. Conclusion and Next Research Steps

**Within these first 131 regular-season starts, Mahomes had the higher observed era-relative QB EPA/dropback, and that lead persisted when the league reference was smoothed over neighboring seasons.** However, the gap was notably smaller than the absolute EPA difference. **Brady's extraordinary 2007 peak and the contrasting career trajectories remain important complementary findings.**

This notebook supports a conclusion about **observed, context-referenced quarterback efficiency in a fixed historical sample**. It does **not** settle who was the better individual player or which quarterback will ultimately have the greater career.

Before treating the measured gap as a strong comparative claim, future work should: **(1)** estimate uncertainty with game-level and preferably season-aware resampling; **(2)** test sensitivity to excluding high-leverage seasons such as Brady 2007 and Mahomes 2018/2022, and to excluding partial 2026; **(3)** examine alternate baselines, including QB-qualified and leave-study-QB-out references; and **(4)** evaluate team and opponent context. These are natural extensions beyond this completed **descriptive era-adjusted analysis**.
