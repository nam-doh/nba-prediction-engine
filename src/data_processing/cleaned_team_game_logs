from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "team_game_logs.csv"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "team_game_logs_clean.csv"
)


REQUIRED_COLUMNS = [
    "SEASON",
    "SEASON_TYPE",
    "GAME_ID",
    "GAME_DATE",
    "TEAM_ID",
    "TEAM_NAME",
    "MATCHUP",
    "WL",
    "PTS",
]


NUMERIC_COLUMNS = [
    "TEAM_ID",
    "MIN",
    "FGM",
    "FGA",
    "FG_PCT",
    "FG3M",
    "FG3A",
    "FG3_PCT",
    "FTM",
    "FTA",
    "FT_PCT",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
    "PTS",
    "PLUS_MINUS",
]


def load_data() -> pd.DataFrame:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Raw data file was not found:\n{INPUT_FILE}"
        )

    return pd.read_csv(
        INPUT_FILE,
        dtype={
            "GAME_ID": "string",
            "SEASON": "string",
            "SEASON_TYPE": "string",
        },
    )


def validate_columns(df: pd.DataFrame) -> None:
    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )


def clean_identifiers(df: pd.DataFrame) -> pd.DataFrame:
    df["GAME_ID"] = (
        df["GAME_ID"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(10)
    )

    df["TEAM_ID"] = pd.to_numeric(
        df["TEAM_ID"],
        errors="coerce",
    ).astype("Int64")

    return df


def clean_dates(df: pd.DataFrame) -> pd.DataFrame:
    df["GAME_DATE"] = pd.to_datetime(
        df["GAME_DATE"],
        errors="coerce",
    )

    return df


def clean_numeric_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    available_numeric_columns = [
        column
        for column in NUMERIC_COLUMNS
        if column in df.columns
    ]

    for column in available_numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    return df


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    df["WIN"] = df["WL"].map(
        {
            "W": 1,
            "L": 0,
        }
    ).astype("Int64")

    df["HOME_GAME"] = (
        df["MATCHUP"]
        .astype("string")
        .str.contains(
            "vs.",
            regex=False,
            na=False,
        )
        .astype("int8")
    )

    df["AWAY_GAME"] = (
        1 - df["HOME_GAME"]
    ).astype("int8")

    df["OPPONENT_ABBREVIATION"] = (
        df["MATCHUP"]
        .astype("string")
        .str.extract(
            r"(?:vs\.|@)\s+([A-Z]{3})",
            expand=False,
        )
    )

    df["TEAM_GAME_NUMBER"] = (
        df.sort_values(
            [
                "SEASON",
                "TEAM_ID",
                "GAME_DATE",
                "GAME_ID",
            ]
        )
        .groupby(
            [
                "SEASON",
                "TEAM_ID",
            ]
        )
        .cumcount()
        .add(1)
    )

    return df


def remove_invalid_rows(
    df: pd.DataFrame,
) -> pd.DataFrame:
    df = df.dropna(
        subset=[
            "SEASON",
            "GAME_ID",
            "GAME_DATE",
            "TEAM_ID",
            "TEAM_NAME",
            "MATCHUP",
            "WL",
            "WIN",
        ]
    )

    df = df[
        df["WL"].isin(
            [
                "W",
                "L",
            ]
        )
    ]

    return df


def remove_duplicates(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    rows_before = len(df)

    df = df.drop_duplicates(
        subset=[
            "SEASON",
            "SEASON_TYPE",
            "GAME_ID",
            "TEAM_ID",
        ],
        keep="first",
    )

    rows_removed = rows_before - len(df)

    return df, rows_removed


def sort_data(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.sort_values(
            [
                "GAME_DATE",
                "GAME_ID",
                "TEAM_ID",
            ]
        )
        .reset_index(drop=True)
    )


def validate_clean_data(
    df: pd.DataFrame,
) -> None:
    duplicate_count = df.duplicated(
        subset=[
            "SEASON",
            "GAME_ID",
            "TEAM_ID",
        ]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            f"Found {duplicate_count} duplicate team-game rows."
        )

    if df["WIN"].isna().any():
        raise ValueError(
            "The WIN column contains missing values."
        )

    if df["GAME_DATE"].isna().any():
        raise ValueError(
            "The GAME_DATE column contains invalid dates."
        )

    if not df["WIN"].isin([0, 1]).all():
        raise ValueError(
            "The WIN column contains values other than 0 or 1."
        )


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = load_data()

    print(f"Raw rows: {len(df):,}")
    print(f"Raw columns: {len(df.columns):,}")

    validate_columns(df)

    df = clean_identifiers(df)
    df = clean_dates(df)
    df = clean_numeric_columns(df)
    df = create_features(df)
    df = remove_invalid_rows(df)

    df, duplicates_removed = remove_duplicates(df)

    df = sort_data(df)

    df["TEAM_GAME_NUMBER"] = (
        df.groupby(
            [
                "SEASON",
                "TEAM_ID",
            ]
        )
        .cumcount()
        .add(1)
    )

    validate_clean_data(df)

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        date_format="%Y-%m-%d",
    )

    summary = (
        df.groupby("SEASON")
        .agg(
            TEAM_GAME_ROWS=("GAME_ID", "size"),
            UNIQUE_GAMES=("GAME_ID", "nunique"),
            TEAMS=("TEAM_ID", "nunique"),
            FIRST_GAME=("GAME_DATE", "min"),
            LAST_GAME=("GAME_DATE", "max"),
        )
        .reset_index()
        .sort_values("SEASON")
    )

    print("\nCleaning complete.")
    print(f"Clean rows: {len(df):,}")
    print(f"Duplicates removed: {duplicates_removed:,}")
    print(f"Clean columns: {len(df.columns):,}")

    print("\nSeason summary:")
    print(summary.to_string(index=False))

    print(f"\nClean data saved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()