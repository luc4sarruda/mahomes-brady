
from pathlib import Path
from datetime import datetime, timezone

import nflreadpy as nfl
import polars as pl


# Project configuration
ROOT = Path(__file__).resolve().parents[1]

SCHEDULE_DIR = ROOT / "data" / "raw" / "schedules"
PBP_DIR = ROOT / "data" / "raw" / "play_by_play"

SEASONS = (
    list(range(2001, 2011))
    + list(range(2017, 2027))
)

SCHEDULE_DIR.mkdir(parents=True, exist_ok=True)
PBP_DIR.mkdir(parents=True, exist_ok=True)


def download_schedules():
    output = SCHEDULE_DIR / "schedules.parquet"

    if output.exists():
        print("Schedules already downloaded.")
        return

    print("Downloading NFL schedules...")

    schedules = nfl.load_schedules(seasons=SEASONS)
    schedules.write_parquet(output)

    print(f"Saved: {output}")
    print(f"Shape: {schedules.shape}")


def download_pbp():
    for season in SEASONS:
        output = PBP_DIR / f"pbp_{season}.parquet"

        if output.exists():
            print(f"Skipping {season}: file exists.")
            continue

        print(f"Downloading PBP: {season}")

        pbp = nfl.load_pbp(seasons=[season])
        pbp.write_parquet(output)

        print(f"Saved: {output}")
        print(f"Shape: {pbp.shape}")


def inspect_data():
    schedules = pl.read_parquet(
        SCHEDULE_DIR / "schedules.parquet"
    )

    print("\n=== SCHEDULES ===")
    print("Shape:", schedules.shape)
    print("Columns:", schedules.columns)

    pbp_2018 = pl.read_parquet(
        PBP_DIR / "pbp_2018.parquet"
    )

    print("\n=== PBP 2018 ===")
    print("Shape:", pbp_2018.shape)
    print("Columns:", pbp_2018.columns)


if __name__ == "__main__":
    started_at = datetime.now(timezone.utc)
    print(f"Download started at: {started_at.isoformat()}")

    download_schedules()
    download_pbp()
    inspect_data()

    finished_at = datetime.now(timezone.utc)
    print(f"\nDownload completed at: {finished_at.isoformat()}")
