# Can the Baby GOAT Surpass the GOAT?

### Tom Brady vs. Patrick Mahomes: A Data-Driven NFL Career Comparison

## Overview

This project explores the early careers of Tom Brady and Patrick Mahomes through an era-adjusted statistical comparison of their first 131 regular-season starts.

Both quarterbacks reached 100 regular-season wins in 131 starts. However, similar records do not necessarily imply similar individual performance or team circumstances.

The study investigates differences in efficiency, career progression, and team context using historical NFL data.

## Research Questions

1. How do their individual performances compare when adjusted for NFL era differences?
2. How did their efficiency evolve across their first 131 starts?
3. What role did team context play in their respective winning records?

## Data Sources

- nflverse / nflfastR
- NFL game schedules
- NFL play-by-play data
- Historical NFL records for independent validation

## Methodology

The analysis focuses on regular-season games and uses reproducible Python data pipelines.

The study emphasizes data quality, transparent statistical definitions, and era-adjusted comparisons.

See [Research Protocol](research_protocol.md) for the complete methodology.

## Tech Stack

Python · Polars · pandas · NumPy · Matplotlib · Seaborn · SciPy · Jupyter

## Project Status

**In progress — Data collection and validation**

- [x] Research protocol
- [x] Historical data acquisition
- [x] First 131 starts identified and validated
- [ ] Individual passing statistics
- [ ] Era-adjusted efficiency analysis
- [ ] Data visualization
- [ ] Final research report

## Reproducibility

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Download the required NFL data:

```bash
python scripts/download_data.py
```

Build the validated master table:

```bash
python scripts/create_master_table.py
```

## Limitations

This is an observational historical study. Individual quarterback performance cannot be completely separated from team context, coaching, opponents, and differences between NFL eras.

The study does not attempt to forecast future championships or determine a definitive greatest-of-all-time ranking.