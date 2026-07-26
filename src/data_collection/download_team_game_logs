from pathlib import Path
import time

import pandas as pd
from nba_api.stats.endpoints import leaguegamelog


SEASONS = [
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
    "2025-26",
]

SEASON_TYPE = "Regular Season"
REQUEST_DELAY_SECONDS = 3
MAX_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 60

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIRECTORY = PROJECT_ROOT / "data" / "raw"
OUTPUT_FILE = RAW_DATA_DIRECTORY / "team_game_logs.csv"


def download_one_season(
    season: str,
    season_type: str,
) -> pd.DataFrame:
    print(f"Downloading {season} {season_type}...")

    response = leaguegamelog.LeagueGameLog(
        season=season,
        season_type_all_star=season_type,
        player_or_team_abbreviation="T",
        sorter="DATE",
        direction="ASC",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    season_df = response.get_data_frames()[0].copy()

    if season_df.empty:
        raise ValueError(
            f"The NBA API returned zero rows for {season}."
        )

    season_df["SEASON"] = season
    season_df["SEASON_TYPE"] = season_type

    print(
        f"Completed {season}: "
        f"{len(season_df):,} team-game rows"
    )

    return season_df


def download_with_retries(
    season: str,
    season_type: str,
) -> pd.DataFrame:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return download_one_season(
                season=season,
                season_type=season_type,
            )

        except Exception as error:
            print(
                f"Attempt {attempt} of {MAX_RETRIES} failed "
                f"for {season}."
            )
            print(f"Error: {error}")

            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Unable to download {season} after "
                    f"{MAX_RETRIES} attempts."
                ) from error

            wait_time = REQUEST_DELAY_SECONDS * attempt

            print(
                f"Waiting {wait_time} seconds before retrying..."
            )

            time.sleep(wait_time)

    raise RuntimeError(
        f"Unexpected download failure for {season}."
    )


def validate_download(df: pd.DataFrame) -> None:
    required_columns = {
        "GAME_ID",
        "GAME_DATE",
        "TEAM_ID",
        "TEAM_NAME",
        "MATCHUP",
        "WL",
        "PTS",
        "SEASON",
        "SEASON_TYPE",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "The downloaded data is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    if df.empty:
        raise ValueError(
            "The combined dataset contains zero rows."
        )


def main() -> None:
    RAW_DATA_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    downloaded_seasons = []

    for index, season in enumerate(SEASONS):
        season_df = download_with_retries(
            season=season,
            season_type=SEASON_TYPE,
        )

        downloaded_seasons.append(season_df)

        if index < len(SEASONS) - 1:
            print(
                f"Waiting {REQUEST_DELAY_SECONDS} seconds "
                "before the next request...\n"
            )

            time.sleep(REQUEST_DELAY_SECONDS)

    combined_df = pd.concat(
        downloaded_seasons,
        ignore_index=True,
    )

    validate_download(combined_df)

    combined_df["GAME_ID"] = (
        combined_df["GAME_ID"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(10)
    )

    rows_before_deduplication = len(combined_df)

    combined_df = combined_df.drop_duplicates(
        subset=[
            "SEASON",
            "SEASON_TYPE",
            "GAME_ID",
            "TEAM_ID",
        ],
        keep="first",
    )

    rows_removed = (
        rows_before_deduplication
        - len(combined_df)
    )

    combined_df["GAME_DATE"] = pd.to_datetime(
        combined_df["GAME_DATE"],
        errors="coerce",
    )

    combined_df = combined_df.sort_values(
        by=[
            "GAME_DATE",
            "GAME_ID",
            "TEAM_ID",
        ]
    ).reset_index(drop=True)

    combined_df["GAME_DATE"] = (
        combined_df["GAME_DATE"]
        .dt.strftime("%Y-%m-%d")
    )

    combined_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    season_summary = (
        combined_df
        .groupby("SEASON")
        .agg(
            TEAM_GAME_ROWS=("GAME_ID", "size"),
            UNIQUE_GAMES=("GAME_ID", "nunique"),
            TEAMS=("TEAM_ID", "nunique"),
        )
        .reset_index()
        .sort_values("SEASON")
    )

    print("\nDownload complete.")
    print(f"Total rows: {len(combined_df):,}")
    print(f"Duplicate rows removed: {rows_removed:,}")
    print(f"Total columns: {len(combined_df.columns):,}")

    print("\nSeason summary:")
    print(season_summary.to_string(index=False))

    print(f"\nRaw data saved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()