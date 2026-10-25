# Data Dictionary

**Project:** Can the Baby GOAT Surpass the GOAT?  
**Status:** Working documentation, version 1.0  
**Analysis unit:** A quarterback's regular-season start; play-level data support individual performance metrics.

## 1. Datasets and Relationships

| Dataset | Grain | Identifier | Local file |
|---|---|---|---|
| NFL schedules | One row per NFL game | `game_id` | `data/raw/schedules/schedules.parquet` |
| NFL play-by-play (PBP) | One row per recorded play/event | `game_id` + `play_id` (and `drive` when required) | `data/raw/play_by_play/pbp_{season}.parquet` |
| Validated QB starts | One row per quarterback start | (`player_id`, `game_id`) | `data/processed/qb_first_131_starts.parquet` |

The schedules and play-by-play tables are related through `game_id` (one game to many play/event records). Join PBP records to the validated game sample using `game_id`, then attribute individual plays using the relevant player IDs. Never assign all of a team's plays to its starting quarterback.

## 2. Schedules — Selected Source Fields

| Column | Typical type | Meaning | Important notes |
|---|---|---|---|
| `game_id` | String | Human-readable game key, e.g. `2005_17_MIA_NE` | Primary join key; use as a string |
| `season` | Integer | NFL season year | January games can belong to the previous season |
| `week` | Integer | NFL season week | Not a reliable standalone playoff/regular-season filter |
| `game_type` | String | Game type (`REG`, `WC`, `DIV`, `CON`, `SB`) | Filter to `REG` |
| `gameday` | String/date | Calendar date of the game | Parsed into `game_date` |
| `home_team` | String | Designated home team abbreviation | May include neutral-site games |
| `away_team` | String | Away team abbreviation | — |
| `home_score` | Integer/nullable | Home team's final points | Can be missing for unplayed games |
| `away_score` | Integer/nullable | Away team's final points | Can be missing for unplayed games |
| `home_qb_id` | String/nullable | GSIS ID of designated home starting QB | Check against independent records if suspicious |
| `away_qb_id` | String/nullable | GSIS ID of designated away starting QB | Check against independent records if suspicious |
| `home_qb_name` | String/nullable | Designated home starting QB | Descriptive only; not a unique key |
| `away_qb_name` | String/nullable | Designated away starting QB | Descriptive only; not a unique key |

## 3. Play-by-Play — Selected Source Fields

| Column | Typical type | Meaning | Important notes |
|---|---|---|---|
| `game_id` | String | Corresponding game identifier | Relate to schedules using `game_id` |
| `play_id` | Numeric | Play identifier | Along with `game_id` and, when appropriate, `drive`, identifies a play |
| `season` | Integer | NFL season | Keep consistent with schedule season |
| `season_type` | String | `REG` or `POST` | Use `REG` |
| `posteam` | String/nullable | Team with possession | Often missing for non-offensive events |
| `defteam` | String/nullable | Defending team | May be missing for certain events |
| `passer_player_id` | String/nullable | ID of player credited with a pass | Not necessarily populated on sacks/scrambles |
| `passer_player_name` | String/nullable | Name of passer | Do not use as the primary identity key |
| `pass_attempt` | Numeric indicator | nflverse pass-attempt classification | **Not automatically identical to official passing attempts**; includes sacks in some nflverse definitions |
| `qb_dropback` | Numeric indicator | Quarterback dropback classification | Includes passes, sacks, and scrambles under the dataset definition |
| `passing_yards` | Numeric/nullable | Credited passing yards on a play | Not a QB season total |
| `pass_touchdown` | Numeric indicator | Passing touchdown | May be null for inapplicable records |
| `interception` | Numeric indicator | Interception | Confirm denominator when computing INT% |
| `epa` | Float/nullable | Expected Points Added for the play | Model-based team/possession value, not pure individual ability |
| `qb_epa` | Float/nullable | EPA adjusted for QB attribution where provided | Confirm coverage and field semantics before using |
| `air_yards` | Numeric/nullable | Air distance of a pass to its target | Coverage/availability can vary by season |

The PBP table includes non-offensive records. Null values are not automatically errors; inspect each field's applicability before removing or imputing values.

## 4. Processed Master Table — Output Fields

The output of `scripts/create_master_table.py` is a **derived** dataset. Its names are intentionally normalized so each row describes the quarterback's own team, regardless of venue.

| Field | Meaning | Derivation |
|---|---|---|
| `player_id` | Verified GSIS identifier | Starting QB ID, with documented correction where necessary |
| `player_name` | Full QB name | Lookup from configured player identities |
| `start_no` | Chronological regular-season start number | 1 to 131 per player |
| `game_id` | Source game identifier | Schedules |
| `game_date` | Game date | Parsed from `gameday` |
| `season` | NFL season | Schedules |
| `week` | NFL week | Schedules |
| `team` | QB's team | `home_team` or `away_team`, depending on QB side |
| `opponent` | Opponent | Other team in game |
| `home_away` | QB's side | `HOME` or `AWAY` |
| `points_for` | QB team's final score | Home or away score based on QB side |
| `points_against` | Opponent's final score | Opposing score |
| `point_diff` | Team scoring margin | `points_for - points_against` |
| `result` | Team's result for QB start | `W`, `L`, or `T` |
| `cumulative_wins` | Wins through this start | Running count of `result == 'W'` |
| `cumulative_losses` | Losses through this start | Running count of `result == 'L'` |

## 5. Identity and Known Source Exception

| Player | GSIS ID | Sample |
|---|---|---|
| Tom Brady | `00-0019596` | First 131 regular-season starts |
| Patrick Mahomes | `00-0033873` | First 131 regular-season starts |

**Documented exception — `2005_17_MIA_NE` (January 1, 2006):** The schedules dataset identifies Matt Cassel (`00-0023662`) as New England's starting QB, but Tom Brady started and was replaced during the game. The processing script corrects **only the starting-QB attribution for this game**, preserving the raw schedules file. This affects Brady's start count and team win/loss attribution, **not** the individual passing plays credited to Brady or Cassel. Keep this correction in `docs/data_quality_log.md` as well.

## 6. Planned Analytical Metrics

| Metric | Definition | Denominator / caution |
|---|---|---|
| QB starter record | Wins, losses, ties across first 131 starts | Team result, not isolated QB contribution |
| Passing yards per attempt (Y/A) | Passing yards / official pass attempts | Reconcile attempts with box-score conventions |
| Passing TD rate | Passing touchdowns / official pass attempts | Passing TDs only |
| Interception rate | Interceptions thrown / official pass attempts | Not interceptions per start |
| EPA per dropback | Sum of QB-attributed EPA / eligible QB dropbacks | Include sacks and scrambles where defined; validate QB attribution |
| Era-relative EPA per dropback | QB EPA/dropback minus season-specific league baseline | Match season and inclusion rules |
| Points allowed per start | Sum of points allowed / starts | Team-level context, not exclusively defense |
| Point differential per start | Sum of `point_diff` / starts | Team-level measure |

Do not compute CPOE for a complete cross-era core comparison without first demonstrating comparable historical coverage.

## 7. Validation Rules

- Exactly 131 unique regular-season starts per player; 262 rows total.
- The 131st start dates are **2010-10-04** (Brady) and **2026-10-18** (Mahomes).
- Each player's record across these starts is **100–31–0**.
- No duplicate (`player_id`, `game_id`) records; no missing values in required master-table fields.
- No unplayed, postseason, or post-cutoff game in the main sample.
- Match PBP to schedules by `game_id`; verify join completeness and individual player attribution.
- Validate official passing totals independently before publishing rates.
- Record missingness and per-season coverage; never replace inapplicable advanced metrics with zero.

## 8. Documentation and References

- [nflreadr Schedules Data Dictionary](https://nflreadr.nflverse.com/articles/dictionary_schedules.html)
- [nflfastR Play-by-Play Field Descriptions](https://nflfastr.com/articles/field_descriptions.html)
- [nflreadpy](https://nflreadpy.nflverse.com/)
- [Research Protocol](../research_protocol.md)

**Maintenance note:** Types above are typical expected types; check `DataFrame.schema` for the exact types and field availability in each downloaded version. Update this dictionary if the pipeline's selected fields change.


---

## Game-Level Passing Statistics (Added October 25, 2026)

**Dataset:** `data/processed/qb_game_stats.parquet`  
**Grain:** One quarterback × game started (262 rows expected).  
**Join:** `(player_id, game_id)` to `qb_first_131_starts.parquet`.

| Field | Definition |
|---|---|
| `attempts` | Official-style passing attempts; includes quarterback clock-stopping spikes, excludes sacks and scrambles |
| `completions` | Completed credited pass attempts |
| `passing_yards` | Passing yards credited to the actual passer |
| `passing_tds` | Passing touchdowns thrown |
| `interceptions` | Interceptions thrown |
| `completion_pct` | 100 × completions / attempts |
| `yards_per_attempt` | passing_yards / attempts |
| `td_rate` | 100 × passing_tds / attempts |
| `int_rate` | 100 × interceptions / attempts |

Rates are undefined (`null`) for games with zero pass attempts. QB substitutions are handled by play-level player IDs; the starting QB does not inherit the replacement QB's production. To understand exact filters, data-quality checks, and the distinction between a source-consistency check and independent box-score verification, see [`passing_statistics_validation.md`](passing_statistics_validation.md).

**External reference fields (nflverse weekly player stats):** `attempts`, `completions`, `passing_yards`, `passing_tds`, `passing_interceptions`. Source dictionary: https://nflreadr.nflverse.com/articles/dictionary_player_stats.html.


## Passing Statistics — Validation Status (October 25, 2026)

The user reported that `scripts/create_player_stats.py` and `scripts/validate_passing_stats.py` completed successfully, with all 262 quarterback-start records matching the weekly nflverse reference on the five integer passing statistics. Selected game box scores were also manually reviewed with no reported discrepancies; the specific external sample and URLs are not yet recorded. This is **not** proof that all 262 box scores were independently checked.

**Derived datasets and grain:**

| Dataset | Grain | Validation / purpose |
|---|---|---|
| `qb_first_131_starts.parquet` | One QB start | Defines 262 eligible games |
| `qb_pass_attempts.parquet` | One credited pass attempt | Auditable selection, including QB spikes |
| `qb_game_stats.parquet` | One QB start | Passing metrics, including zero-attempt starts if applicable |
| `qb_master_stats.parquet` | One QB start | Game context joined to passing stats |

**Rules:** Aggregate `completions`, `attempts`, `passing_yards`, `passing_tds`, and `interceptions` before calculating overall rates; never average game-level percentages without weighting. The QB's start does not imply ownership of a replacement's passing attempts. A spike counts as an incomplete official pass attempt. Keep `qb_dropback`/EPA separate from official passing attempts. See [Passing Statistics Validation](passing_statistics_validation.md) and [Data Quality Log](data_quality_log.md).
