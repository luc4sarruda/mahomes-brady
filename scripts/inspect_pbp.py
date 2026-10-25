
from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
PBP_DIR = ROOT / "data" / "raw" / "play_by_play"

SEASONS = [2001, 2005, 2010, 2018, 2025, 2026]

REQUIRED_COLUMNS = [
    "game_id",
    "play_id",
    "season",
    "season_type",
    "passer_player_id",
    "passer_player_name",
    "pass_attempt",
    "complete_pass",
    "passing_yards",
    "pass_touchdown",
    "interception",
    "sack",
    "qb_dropback",
    "qb_scramble",
    "epa",
    "qb_epa",
]


def inspect_season(season: int) -> None:
    path = PBP_DIR / f"pbp_{season}.parquet"

    if not path.exists():
        print(f"\n{season}: FILE NOT FOUND")
        return

    # Read only metadata, without loading the full dataset
    dataset = pl.scan_parquet(path)
    schema = dataset.collect_schema()

    print(f"\n{'=' * 45}")
    print(f"SEASON: {season}")
    print(f"{'=' * 45}")

    missing = []

    for column in REQUIRED_COLUMNS:
        if column in schema:
            print(f"[OK] {column}: {schema[column]}")
        else:
            print(f"[MISSING] {column}")
            missing.append(column)

    print(f"\nMissing columns: {len(missing)}")


def main() -> None:
    for season in SEASONS:
        inspect_season(season)


if __name__ == "__main__":
    main()
