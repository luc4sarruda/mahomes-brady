"""Build the first 131 regular-season starts for Brady and Mahomes.

Run from the repository root:
    python3 scripts/create_master_table.py

Input:
    data/raw/schedules/schedules.parquet
Outputs:
    data/processed/qb_first_131_starts.parquet
    data/processed/qb_first_131_starts.csv
    data/processed/starter_attribution_audit.csv
"""

from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
SCHEDULES_PATH = ROOT / "data/raw/schedules/schedules.parquet"
OUTPUT_DIR = ROOT / "data/processed"

PLAYERS = {
    "Tom Brady": "00-0019596",
    "Patrick Mahomes": "00-0033873",
}
START_LIMIT = 131
EXPECTED_RECORD = (100, 31, 0)  # Wins, losses, ties at start 131

# Documented source-data exception: Brady started this game, but the
# schedules dataset incorrectly identifies Matt Cassel as the starter.
BRADY_START_CORRECTION = "2005_17_MIA_NE"


def load_schedules() -> pl.DataFrame:
    if not SCHEDULES_PATH.is_file():
        raise FileNotFoundError(f"Schedules dataset not found: {SCHEDULES_PATH}")

    games = pl.read_parquet(SCHEDULES_PATH)
    required = {
        "game_id", "gameday", "season", "week", "game_type",
        "home_team", "away_team", "home_score", "away_score",
        "home_qb_id", "away_qb_id", "home_qb_name", "away_qb_name",
    }
    missing = required - set(games.columns)
    if missing:
        raise ValueError(f"Missing schedule columns: {sorted(missing)}")

    games = (
        games.with_columns(
            pl.col("gameday")
            .cast(pl.String)
            .str.strptime(pl.Date, format="%Y-%m-%d")
            .alias("game_date")
        )
        .filter(
            (pl.col("game_type") == "REG")
            & pl.col("home_score").is_not_null()
            & pl.col("away_score").is_not_null()
        )
    )

    if games["game_id"].n_unique() != games.height:
        raise ValueError("Duplicate game_id values in schedules")
    return games


def build_starters(games: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    shared = ["game_id", "game_date", "season", "week"]

    home = games.select(
        *shared,
        pl.col("home_qb_id").cast(pl.String).alias("source_qb_id"),
        pl.col("home_qb_name").alias("source_qb_name"),
        pl.col("home_team").alias("team"),
        pl.col("away_team").alias("opponent"),
        pl.lit("HOME").alias("home_away"),
        pl.col("home_score").alias("points_for"),
        pl.col("away_score").alias("points_against"),
    )
    away = games.select(
        *shared,
        pl.col("away_qb_id").cast(pl.String).alias("source_qb_id"),
        pl.col("away_qb_name").alias("source_qb_name"),
        pl.col("away_team").alias("team"),
        pl.col("home_team").alias("opponent"),
        pl.lit("AWAY").alias("home_away"),
        pl.col("away_score").alias("points_for"),
        pl.col("home_score").alias("points_against"),
    )
    starters = pl.concat([home, away])

    # A single, explicitly documented correction, scoped to the home QB.
    correction = (
        (pl.col("game_id") == BRADY_START_CORRECTION)
        & (pl.col("home_away") == "HOME")
    )
    affected = starters.filter(correction)
    if affected.height != 1 or affected.item(0, "team") != "NE":
        raise ValueError("Could not uniquely identify the Brady/Cassel game")

    audit = affected.select(
        "game_id", "game_date", "source_qb_id", "source_qb_name"
    ).with_columns(
        pl.lit(PLAYERS["Tom Brady"]).alias("corrected_qb_id"),
        pl.lit("Tom Brady").alias("corrected_qb_name"),
    )

    starters = starters.with_columns(
        pl.when(correction)
        .then(pl.lit(PLAYERS["Tom Brady"]))
        .otherwise(pl.col("source_qb_id"))
        .alias("player_id")
    ).with_columns(
        (pl.col("points_for") - pl.col("points_against")).alias("point_diff"),
        pl.when(pl.col("points_for") > pl.col("points_against"))
        .then(pl.lit("W"))
        .when(pl.col("points_for") < pl.col("points_against"))
        .then(pl.lit("L"))
        .otherwise(pl.lit("T"))
        .alias("result"),
    )
    return starters, audit


def select_player_starts(starters: pl.DataFrame, name: str, player_id: str) -> pl.DataFrame:
    player_starts = (
        starters.filter(pl.col("player_id") == player_id)
        .sort(["game_date", "game_id"])
        .head(START_LIMIT)
        .with_row_index("start_no", offset=1)
        .with_columns(pl.lit(name).alias("player_name"))
        .with_columns(
            (pl.col("result") == "W").cast(pl.Int64).cum_sum().alias("cumulative_wins"),
            (pl.col("result") == "L").cast(pl.Int64).cum_sum().alias("cumulative_losses"),
        )
    )

    if player_starts.height != START_LIMIT:
        raise ValueError(f"{name}: found {player_starts.height} starts, expected {START_LIMIT}")
    if player_starts["game_id"].n_unique() != START_LIMIT:
        raise ValueError(f"{name}: duplicate games in selected starts")

    record = tuple(player_starts.filter(pl.col("result") == r).height for r in ("W", "L", "T"))
    first_date = player_starts.item(0, "game_date")
    last_date = player_starts.item(START_LIMIT - 1, "game_date")
    print(f"{name}: {record[0]}-{record[1]}-{record[2]} | {first_date} to {last_date}")
    if record != EXPECTED_RECORD:
        raise ValueError(f"{name}: expected {EXPECTED_RECORD}, got {record}")

    return player_starts.select(
        "player_id", "player_name", "start_no", "game_id", "game_date",
        "season", "week", "team", "opponent", "home_away",
        "points_for", "points_against", "point_diff", "result",
        "cumulative_wins", "cumulative_losses",
    )


def main() -> None:
    starters, audit = build_starters(load_schedules())
    master = pl.concat([
        select_player_starts(starters, name, player_id)
        for name, player_id in PLAYERS.items()
    ])

    if master.height != 2 * START_LIMIT:
        raise ValueError("Unexpected number of rows in the master table")
    if master.select("player_id", "game_id").unique().height != master.height:
        raise ValueError("Duplicate player-game pair in the master table")
    if any(master.null_count().row(0)):
        raise ValueError("Missing values in the master table")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    master.write_parquet(OUTPUT_DIR / "qb_first_131_starts.parquet")
    master.write_csv(OUTPUT_DIR / "qb_first_131_starts.csv")
    audit.write_csv(OUTPUT_DIR / "starter_attribution_audit.csv")
    print(f"\nValidated {master.height} starts. Master table and audit saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
