# Descriptive Analysis — Methodology and Deliverables

**Project:** Can the Baby GOAT Surpass the GOAT?  
**Phase:** Initial descriptive analysis (before era adjustment)

## Study Population

- Tom Brady: first 131 NFL regular-season starts.
- Patrick Mahomes: first 131 NFL regular-season starts.
- Exactly 262 quarterback-game records total, selected using the audited master table.
- Individual statistics are credited to the actual passer/rusher; backup production does not transfer to the starter.
- All previously documented source-specific corrections must remain auditable upstream.

## Input Tables and Data Lineage

| Dataset | Grain | Purpose |
|---|---|---|
| `qb_first_131_starts.parquet` | QB x game started | Sample, chronology, team result and points |
| `qb_game_stats.parquet` | QB x game started | Validated passing counts |
| `qb_rushing_stats.parquet` | QB x game started | Validated rushing, kneel, scramble and sack counts |
| `qb_complete_stats.parquet` | QB x game started | Validated join of all three inputs |

**Join keys:** `(player_id, game_id)`, with consistency checks for `player_name`, `season`, `week`, and `start_no`. Missing records, duplicate keys, or inconsistent identity metadata cause the pipeline to fail.

## Metrics

- Completion % = `100 * sum(completions) / sum(attempts)`.
- Passing Y/A = `sum(passing_yards) / sum(attempts)`.
- Passing TD % = `100 * sum(passing_tds) / sum(attempts)`.
- INT % = `100 * sum(interceptions) / sum(attempts)`.
- Rushing YPC = `sum(rushing_yards) / sum(carries)`, includes kneels if recorded as rushes.
- Non-kneel rushing YPC = `sum(non_kneel_yards) / sum(non_kneel_carries)`.
- Scramble share of non-kneel carries = `100 * sum(scrambles) / sum(non_kneel_carries)`.
- Sacks taken per start = `sum(sacks_taken) / 131`; this is descriptive, **not** sack rate per dropback.
- Cumulative wins come from the starting quarterback's team's game result, not individual scoring credit.

Aggregate integer counts **before** calculating any rate. Do not take an unweighted mean of game rates. For zero denominators, rates are undefined (`null`), not zero.

## Planned Figures

1. `01_road_to_100_wins.png` — Cumulative wins versus regular-season start number.
2. `02_passing_production.png` — Completion %, Y/A, passing TD %, interception %.
3. `03_rushing_mobility.png` — Rushing attempts, scrambles and sacks taken (separate comparisons).

## Limitations and Scientific Claims

These are *descriptive*, not era-adjusted, analyses. Interpret all passing rates with caution across 2001–2010 and 2017–2026. Do not claim QB superiority from team wins or sacks taken. Scrambles are included in official rushing attempts; do not add them as a second rushing contribution. Any model-based QB EPA comparisons must be developed in a separately validated phase.

## Acceptance Criteria

- Exactly 262 unique player-game records, 131 per player.
- Complete join keys and matching start numbering across source datasets.
- No missing integer aggregate counts after the merge.
- Recomputed rates use aggregated denominators and distinguish zero denominators.
- Three descriptive figures saved to `reports/figures/`.
- A summary CSV saved to `reports/descriptive_summary.csv`.
- Findings are filled **after** running the analysis, without unsupported causal language.

## Execution

From the repository root:

```bash
python3 scripts/build_complete_qb_stats.py
jupyter lab
```

Open `notebooks/02_descriptive_analysis.ipynb` and run all cells.
