# Data Sources and Provenance

**Project:** Can the Baby GOAT Surpass the GOAT?  
**Status:** Data collection and validation  
**Research snapshot cutoff:** October 18, 2026

## 1. Purpose

This document identifies the original sources, collection methods, coverage, storage, and validation rules for the analysis of the first 131 regular-season NFL starts by Tom Brady and Patrick Mahomes.

**Data provenance is distinct from data quality:** provenance identifies where the records came from; quality checks evaluate whether those records support the analysis.

## 2. Primary Datasets

### 2.1 NFL Schedules and Game Results

- **Provider:** nflverse (schedules/game metadata).
- **Python access:** `nflreadpy.load_schedules(seasons=SEASONS)`.
- **Documentation:** https://nflreadr.nflverse.com/articles/dictionary_schedules.html
- **Loader documentation:** https://nflreadpy.nflverse.com/api/load_functions/
- **Seasons acquired:** 2001–2010 and 2017–2026.
- **Local storage:** `data/raw/schedules/schedules.parquet`.
- **Format:** Parquet.
- **Grain:** One record per game.
- **Use:** Identify starting quarterbacks, game dates, teams, opponents, final scores, and wins/losses.
- **Critical fields:** `game_id`, `season`, `week`, `gameday`, `game_type`, `home_team`, `away_team`, `home_score`, `away_score`, `home_qb_id`, `away_qb_id`.

**Filtering rule:** Include only played regular-season games (`game_type == 'REG'`) with a game date no later than 2026-10-18. Select each QB's first 131 starts in chronological order. January calendar dates remain associated with the appropriate prior NFL season.

### 2.2 NFL Play-by-Play

- **Provider:** nflverse / nflfastR.
- **Python access:** `nflreadpy.load_pbp(seasons=[season])`.
- **Documentation:** https://nflfastr.com/articles/field_descriptions.html
- **Loader documentation:** https://nflreadpy.nflverse.com/api/load_functions/
- **Seasons acquired:** 2001–2010 and 2017–2026.
- **Local storage:** `data/raw/play_by_play/pbp_{season}.parquet` (one file per season).
- **Format:** Parquet.
- **Grain:** One record per play/event.
- **Use:** Derive passing and dropback statistics, EPA, and career-development measures.
- **Critical fields:** `game_id`, `play_id`, `season_type`, `passer_player_id`, `qb_dropback`, `pass_attempt`, `passing_yards`, `pass_touchdown`, `interception`, `epa`, `qb_epa` (where available).

**Filtering rule:** Regular-season events only, restricted to the games in the validated 131-start master table. Attribute individual events to their actual quarterback; do not automatically assign a starter every snap played by his team.

**Historical comparability:** Some advanced fields have limited historical coverage, and nflfastR definitions may differ from official box-score statistics. Each analytical metric requires a defined denominator and a coverage audit.

## 3. Independent Validation Sources

| Source | Role | URL |
|---|---|---|
| New England Patriots / official NFL records | Verify Brady's starts and the October 4, 2010 milestone | https://www.patriots.com/ |
| Kansas City Chiefs / official NFL records | Verify Mahomes's October 18, 2026 milestone | https://www.chiefs.com/ |
| Pro Football Reference | Independent historical box scores, passing totals, and starter records | https://www.pro-football-reference.com/ |
| nflverse documentation | Field definitions and data-source limitations | https://nflreadr.nflverse.com/ |

When a specific fact requires validation, add a **direct article or box-score URL and access date** to the quality log rather than treating a general homepage as proof.

## 4. Known Data Quality Issue

**Issue ID:** `DQ-001`  
**Game:** `2005_17_MIA_NE`  
**Date:** January 1, 2006  
**Source starter:** Matt Cassel (`00-0023662`)  
**Verified starter:** Tom Brady (`00-0019596`)

The source schedules data misattributes the starting quarterback for this game. Brady started and was replaced by Cassel. The processed data pipeline applies **one explicit, documented exception** to the starter attribution. It **does not edit the raw dataset** and does not reassign Cassel's passing statistics to Brady.

**Impact of uncorrected data:** Brady's first 131 identified starts would end on October 17, 2010 with a 101–30 record, rather than the independently established October 4, 2010 endpoint and 100–31 record.

**Required audit artifact:** `data/processed/starter_attribution_audit.csv` (if emitted by the current pipeline). Document direct corroborating evidence in `docs/data_quality_log.md`.

## 5. Data Processing and Lineage

```text
nflverse schedules ─┐
                   ├─> scripts/create_master_table.py
known exception ───┘                  │
                                      v
                       qb_first_131_starts.parquet
                                      │
nflverse PBP (season files) ──────────┤
                                      v
                     Future passing/EPA analysis
```

- **Raw source data:** `data/raw/` — immutable copies of downloaded files.
- **Processed study data:** `data/processed/` — reproducible outputs generated from raw files.
- **Acquisition script:** `scripts/download_data.py`.
- **Master-table script:** `scripts/create_master_table.py`.
- **Research definitions:** `research_protocol.md` and `docs/data_dictionary.md`.

## 6. Reproducibility Metadata

Complete the following **from the local environment**; these values should not be guessed or filled in retrospectively.

| Property | Recorded value |
|---|---|
| Acquisition timestamp (UTC) | TODO |
| Python version | TODO |
| `nflreadpy` version | TODO |
| `polars` version | TODO |
| Schedules row count | TODO |
| Schedule seasons present | TODO |
| PBP files and per-season row counts | TODO |
| SHA-256 checksums of frozen source files | TODO |
| Missing or incomplete downloads | TODO |
| Known source-data exceptions | `DQ-001` |
| Research cutoff | `2026-10-18` |

The research cutoff refers to **games included in the analysis**, not the actual download timestamp. Because the nflverse dataset may be revised, record an extraction timestamp and file hashes for an exact reproducibility snapshot.

## 7. Verification Checklist

- [ ] The locally downloaded datasets contain the intended seasons.
- [ ] All schedule game IDs are unique within the source snapshot.
- [ ] PBP `game_id` values match schedule entries for the selected games.
- [ ] Each selected quarterback has 131 unique starts, 100 wins, and 31 losses.
- [ ] Brady's 131st start date is 2010-10-04.
- [ ] Mahomes's 131st start date is 2026-10-18.
- [ ] DQ-001 has a documented evidence trail and isolated processing correction.
- [ ] Individual QB statistics exclude replacement-quarterback plays.
- [ ] All published metrics identify numerator, denominator, data coverage, and limitations.

## 8. Licensing, Attribution, and Publication

Cite nflverse, nflfastR, and the applicable original data sources when publishing results. Check the license and redistribution rules for every dataset before sharing it; the main nflverse datasets are generally distributed under Creative Commons attribution terms, but individual data products may differ.

The repository should normally **version scripts, research documentation, and figures**, not large raw or processed datasets. A `.gitignore` can exclude `data/raw/` and `data/processed/`; maintain a reproducible acquisition pipeline instead.

## 9. References

- [nflreadpy Documentation](https://nflreadpy.nflverse.com/)
- [nflreadr Schedule Data Dictionary](https://nflreadr.nflverse.com/articles/dictionary_schedules.html)
- [nflfastR Field Descriptions](https://nflfastr.com/articles/field_descriptions.html)
- [nflverse Data Repository](https://github.com/nflverse/nflverse-data)
- [Pro Football Reference](https://www.pro-football-reference.com/)
