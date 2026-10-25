# Rushing Statistics Validation — Discrepancy Investigation

**Project:** Can the Baby GOAT Surpass the GOAT?  
**Status:** Root causes identified from independent game records; corrected pipeline **awaits a fresh local validation run**.  
**Population:** 262 quarterback starts (Brady and Mahomes), five audited metrics per start.

## Audit summary

- Matching QB-games: **260/262**.
- Nonmatching QB-games: **2**.
- Missing nflverse weekly reference records: **0**.
- Matching the nflverse weekly statistics is a cross-pipeline consistency check, not a fully independent audit.

## DQ-005 — Rushing touchdown attributed to the wrong participant

- **Game:** `2020_15_KC_NO` — December 20, 2020.
- **Quarterback:** Patrick Mahomes (`00-0033873`).
- **Metric:** `rushing_tds`.
- **PBP-derived value:** 1.
- **Weekly reference and independent official game box score:** 0.
- **Cause:** In the fourth quarter, Mahomes ran for 1 yard and lateraled to Le'Veon Bell, who ran 12 more yards and scored. The play-level `rush_touchdown = 1` describes the scoring play, *not* necessarily the identity of the scoring player.
- **Correction:** Calculate individual rushing touchdowns only when `rush_touchdown == 1` **and** `td_player_id == player_id`. Check that the scorer identifier exists before aggregating; do not rewrite the raw PBP.
- **Independent sources:**
  - https://www.pro-football-reference.com/boxscores/202012200nor.htm
  - https://www.neworleanssaints.com/game-day/2020/reg-week15/chiefs-at-saints/scoring-summary
- **Verification status:** Pending rerun of `validate_rushing_stats.py`.

## DQ-006 — Aborted snap and a missing rushing yard

- **Game:** `2023_02_KC_JAX` — September 17, 2023.
- **Quarterback:** Patrick Mahomes (`00-0033873`).
- **Metric:** `rushing_yards`.
- **PBP-derived value:** 29.
- **Weekly reference and independent official game box score:** 30.
- **Likely cause:** Mahomes recovered an aborted center/QB exchange and advanced the ball from the KC 43 to the KC 44, a net gain of 1 yard. The existing pipeline appears to include that carry but derives 0 yards from its `rushing_yards` field.
- **Correction to verify locally:** For the *one identified aborted-snap record*, verify `rushing_yards = 0` and `yards_gained = 1`; then use the latter as the player's credited rushing yards in the processed data. Preserve `source_rushing_yards` and attach a correction reason. If the raw values differ or more than one record matches, stop and investigate.
- **Classification:** An aborted snap is not sufficient evidence of a *designed quarterback run*. Report these as a separate analytical category.
- **Independent sources:**
  - https://www.jaguars.com/game-day/2023/reg-week2/chiefs-at-jaguars/box-score
  - https://www.pro-football-reference.com/boxscores/202309170jax.htm
- **Verification status:** Pending inspection and rerun of the corrected pipeline.

## Required next checks

1. Run `python3 scripts/create_rushing_stats.py` with the corrected code.
2. Inspect the printed identification and correction of the 2023 aborted snap.
3. Run `python3 scripts/validate_rushing_stats.py` with the **same weekly reference cache**, and review all deltas.
4. Require **262/262 matches** (and no missing references) before marking the cross-pipeline audit complete.
5. Cross-check the two affected game rows in `qb_rushing_stats.parquet` and the official box scores.
6. Re-audit any `designed_runs` or `designed_run_yards` conclusions after separately classifying aborted snaps.
7. Note the source data release and extraction dates in the provenance log; do not modify archived raw Parquet files.

**Interpretation:** Passing the rerun resolves two identified discrepancies. It does not establish that every derived mobility category has been independently verified.
