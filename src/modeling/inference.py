"""Read-only, as-of inference over the persisted production pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd


FEATURE_COLUMNS = (
    "HOME_GAME",
    "REST_DAYS",
    "SEASON_WIN_PCT",
    "TEAM_GAME_NUMBER",
    "PTS_ROLL5",
    "FG_PCT_ROLL5",
    "FG3_PCT_ROLL5",
    "FT_PCT_ROLL5",
    "REB_ROLL5",
    "AST_ROLL5",
    "STL_ROLL5",
    "BLK_ROLL5",
    "TOV_ROLL5",
    "PLUS_MINUS_ROLL5",
    "WIN_PCT_ROLL5",
    "OPP_PTS_ROLL5",
    "OPP_FG_PCT_ROLL5",
    "OPP_FG3_PCT_ROLL5",
    "OPP_FT_PCT_ROLL5",
    "OPP_REB_ROLL5",
    "OPP_AST_ROLL5",
    "OPP_STL_ROLL5",
    "OPP_BLK_ROLL5",
    "OPP_TOV_ROLL5",
    "OPP_PLUS_MINUS_ROLL5",
    "OPP_WIN_PCT_ROLL5",
    "OPP_REST_DAYS",
    "PTS_ROLL5_DIFF",
    "FG_PCT_ROLL5_DIFF",
    "FG3_PCT_ROLL5_DIFF",
    "REB_ROLL5_DIFF",
    "AST_ROLL5_DIFF",
    "TOV_ROLL5_DIFF",
    "PLUS_MINUS_ROLL5_DIFF",
    "WIN_PCT_ROLL5_DIFF",
    "REST_DAYS_DIFF",
)

TEAM_STAT_COLUMNS = (
    "PTS_ROLL5",
    "FG_PCT_ROLL5",
    "FG3_PCT_ROLL5",
    "FT_PCT_ROLL5",
    "REB_ROLL5",
    "AST_ROLL5",
    "STL_ROLL5",
    "BLK_ROLL5",
    "TOV_ROLL5",
    "PLUS_MINUS_ROLL5",
    "WIN_PCT_ROLL5",
)

REQUIRED_HISTORY_COLUMNS = (
    "TEAM_NAME",
    "GAME_ID",
    "GAME_DATE",
    "TEAM_GAME_NUMBER",
    "SEASON_WIN_PCT",
    *TEAM_STAT_COLUMNS,
)

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data/processed/team_game_modeling.csv"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models/logistic_regression_production.pkl"
MAX_REST_DAYS = 14


class InferenceError(ValueError):
    """An actionable input, source-data, or persisted-model failure."""


@dataclass(frozen=True)
class Prediction:
    """A validated prediction and the metadata needed to interpret it."""

    home_team: str
    away_team: str
    game_date: pd.Timestamp
    home_win_probability: float
    away_win_probability: float
    home_rest_days: int
    away_rest_days: int
    home_state_date: pd.Timestamp
    away_state_date: pd.Timestamp
    source_last_available_date: pd.Timestamp
    data_cutoff: pd.Timestamp
    model_name: str
    model_artifact: str
    feature_count: int
    assumptions: Mapping[str, str]


class InferenceEngine:
    """Load the existing model and historical feature export without fitting."""

    def __init__(self, history: pd.DataFrame, model: Any, model_path: Path):
        self._history = _validate_history(history)
        self._model = _validate_model(model)
        self._model_path = Path(model_path)
        self._data_cutoff = self._history["GAME_DATE"].max()
        self._teams = tuple(sorted(self._history["TEAM_NAME"].unique()))

    @classmethod
    def from_paths(
        cls,
        data_path: str | Path = DEFAULT_DATA_PATH,
        model_path: str | Path = DEFAULT_MODEL_PATH,
    ) -> "InferenceEngine":
        data_path = Path(data_path)
        model_path = Path(model_path)
        if not data_path.is_file():
            raise InferenceError(f"Historical feature data was not found: {data_path}")
        if not model_path.is_file():
            raise InferenceError(f"Production model was not found: {model_path}")
        try:
            history = pd.read_csv(data_path)
        except Exception as exc:  # pragma: no cover - pandas supplies the detail
            raise InferenceError(f"Could not read historical feature data: {exc}") from exc
        try:
            model = joblib.load(model_path)
        except Exception as exc:  # pragma: no cover - joblib supplies the detail
            raise InferenceError(f"Could not load the production model: {exc}") from exc
        return cls(history, model, model_path)

    @property
    def available_teams(self) -> tuple[str, ...]:
        return self._teams

    @property
    def data_cutoff(self) -> pd.Timestamp:
        return self._data_cutoff

    @property
    def model_name(self) -> str:
        return "Production Logistic Regression"

    @property
    def model_artifact(self) -> str:
        return self._model_path.name

    @property
    def assumptions(self) -> Mapping[str, str]:
        return {
            "Historical source": "Static team-game feature export; no live data is fetched.",
            "Rest days": "The matchup uses the user-provided whole-number rest inputs (0–14 days).",
            "Player availability": "Injuries, lineups, trades, and player availability are not modeled.",
            "Probability meaning": "Win probabilities are historical-data estimates, not guarantees.",
        }

    def predict_matchup(
        self,
        home_team: str,
        away_team: str,
        game_date: Any,
        home_rest_days: Any,
        away_rest_days: Any,
    ) -> Prediction:
        """Predict a hypothetical game using only rows strictly before ``game_date``."""
        game_date = _parse_game_date(game_date)
        if not isinstance(home_team, str) or not home_team.strip():
            raise InferenceError("Choose a home team.")
        if not isinstance(away_team, str) or not away_team.strip():
            raise InferenceError("Choose an away team.")
        if home_team == away_team:
            raise InferenceError("Choose two different teams.")
        unknown = sorted({home_team, away_team}.difference(self._teams))
        if unknown:
            raise InferenceError(f"Unknown team selection: {', '.join(unknown)}")
        home_rest_days = _parse_rest_days(home_rest_days, "Home")
        away_rest_days = _parse_rest_days(away_rest_days, "Away")

        home_state = self._state_before(home_team, game_date)
        away_state = self._state_before(away_team, game_date)
        features = _build_matchup_features(
            home_state,
            away_state,
            home_rest_days,
            away_rest_days,
            self._history,
            game_date,
        )
        probabilities = self._model.predict_proba(features)
        classes = np.asarray(self._model.classes_)
        positive_positions = np.flatnonzero(classes == 1)
        if len(positive_positions) != 1:
            raise InferenceError("Production model does not expose a binary win class.")
        home_probability = float(probabilities[0, positive_positions[0]])
        away_probability = 1.0 - home_probability
        if (
            not np.isfinite(home_probability)
            or not np.isfinite(away_probability)
            or not 0.0 <= home_probability <= 1.0
            or not 0.0 <= away_probability <= 1.0
            or not np.isclose(home_probability + away_probability, 1.0)
        ):
            raise InferenceError("The production model returned invalid probabilities.")

        source_last_available_date = max(
            home_state["GAME_DATE"], away_state["GAME_DATE"]
        )
        return Prediction(
            home_team=home_team,
            away_team=away_team,
            game_date=game_date,
            home_win_probability=home_probability,
            away_win_probability=away_probability,
            home_rest_days=home_rest_days,
            away_rest_days=away_rest_days,
            home_state_date=home_state["GAME_DATE"],
            away_state_date=away_state["GAME_DATE"],
            source_last_available_date=source_last_available_date,
            data_cutoff=self._data_cutoff,
            model_name=self.model_name,
            model_artifact=self.model_artifact,
            feature_count=len(FEATURE_COLUMNS),
            assumptions=self.assumptions,
        )

    def _state_before(self, team: str, game_date: pd.Timestamp) -> pd.Series:
        prior = self._history[
            (self._history["TEAM_NAME"] == team)
            & (self._history["GAME_DATE"] < game_date)
        ].sort_values(["GAME_DATE", "GAME_ID"])
        if prior.empty:
            raise InferenceError(
                f"No historical team state is available for {team} before {game_date.date()}."
            )
        state = prior.iloc[-1]
        required_state = ["SEASON_WIN_PCT", "TEAM_GAME_NUMBER", *TEAM_STAT_COLUMNS]
        values = pd.to_numeric(state[required_state], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            missing = [column for column in required_state if pd.isna(values[column])]
            detail = ", ".join(missing) if missing else "non-finite feature values"
            raise InferenceError(f"Historical state for {team} is unavailable: {detail}.")
        return state


def predict_matchup(
    home_team: str,
    away_team: str,
    game_date: Any,
    home_rest_days: Any,
    away_rest_days: Any,
    *,
    data_path: str | Path = DEFAULT_DATA_PATH,
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> Prediction:
    """Load the persisted pipeline and predict one hypothetical matchup."""
    engine = InferenceEngine.from_paths(data_path=data_path, model_path=model_path)
    return engine.predict_matchup(
        home_team,
        away_team,
        game_date,
        home_rest_days,
        away_rest_days,
    )


def _validate_history(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        raise InferenceError("Historical feature data is empty.")
    missing = sorted(set(REQUIRED_HISTORY_COLUMNS).difference(history.columns))
    if missing:
        raise InferenceError(f"Historical feature data is missing columns: {', '.join(missing)}")
    checked = history.copy()
    checked["GAME_DATE"] = pd.to_datetime(checked["GAME_DATE"], errors="coerce")
    if checked["GAME_DATE"].isna().any():
        raise InferenceError("Historical feature data contains invalid game dates.")
    if checked["TEAM_NAME"].isna().any() or checked["TEAM_NAME"].astype(str).str.strip().eq("").any():
        raise InferenceError("Historical feature data contains missing team names.")
    if checked["GAME_ID"].isna().any():
        raise InferenceError("Historical feature data contains missing game IDs.")
    return checked


def _validate_model(model: Any) -> Any:
    model_features = getattr(model, "feature_names_in_", None)
    if model_features is None or tuple(model_features) != FEATURE_COLUMNS:
        raise InferenceError(
            "The persisted production model does not match the ordered 36-feature contract."
        )
    if not hasattr(model, "predict_proba") or not hasattr(model, "classes_"):
        raise InferenceError("The persisted production model does not support probability inference.")
    named_steps = getattr(model, "named_steps", {})
    if not {"scaler", "classifier"}.issubset(named_steps):
        raise InferenceError("The persisted production model must contain scaler and classifier steps.")
    return model


def _parse_game_date(value: Any) -> pd.Timestamp:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp) or not isinstance(timestamp, pd.Timestamp):
        raise InferenceError("Enter a valid hypothetical game date.")
    if timestamp.tz is not None:
        raise InferenceError("Hypothetical game date must not include a timezone.")
    return timestamp.normalize()


def _parse_rest_days(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise InferenceError(f"{label} rest days must be a whole number from 0 to {MAX_REST_DAYS}.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise InferenceError(
            f"{label} rest days must be a whole number from 0 to {MAX_REST_DAYS}."
        ) from exc
    if not np.isfinite(numeric) or numeric != int(numeric) or not 0 <= numeric <= MAX_REST_DAYS:
        raise InferenceError(f"{label} rest days must be a whole number from 0 to {MAX_REST_DAYS}.")
    return int(numeric)


def _build_matchup_features(
    home_state: pd.Series,
    away_state: pd.Series,
    home_rest_days: int,
    away_rest_days: int,
    history: pd.DataFrame,
    game_date: pd.Timestamp,
) -> pd.DataFrame:
    row: dict[str, float | int] = {
        "HOME_GAME": 1,
        "REST_DAYS": home_rest_days,
        "SEASON_WIN_PCT": float(home_state["SEASON_WIN_PCT"]),
        "TEAM_GAME_NUMBER": _next_team_game_number(home_state, history, game_date),
        "OPP_REST_DAYS": away_rest_days,
    }
    for stat in TEAM_STAT_COLUMNS:
        row[stat] = float(home_state[stat])
        row[f"OPP_{stat}"] = float(away_state[stat])

    diff_sources = {
        "PTS_ROLL5_DIFF": ("PTS_ROLL5", "OPP_PTS_ROLL5"),
        "FG_PCT_ROLL5_DIFF": ("FG_PCT_ROLL5", "OPP_FG_PCT_ROLL5"),
        "FG3_PCT_ROLL5_DIFF": ("FG3_PCT_ROLL5", "OPP_FG3_PCT_ROLL5"),
        "REB_ROLL5_DIFF": ("REB_ROLL5", "OPP_REB_ROLL5"),
        "AST_ROLL5_DIFF": ("AST_ROLL5", "OPP_AST_ROLL5"),
        "TOV_ROLL5_DIFF": ("TOV_ROLL5", "OPP_TOV_ROLL5"),
        "PLUS_MINUS_ROLL5_DIFF": ("PLUS_MINUS_ROLL5", "OPP_PLUS_MINUS_ROLL5"),
        "WIN_PCT_ROLL5_DIFF": ("WIN_PCT_ROLL5", "OPP_WIN_PCT_ROLL5"),
    }
    for difference, (team_column, opponent_column) in diff_sources.items():
        row[difference] = row[team_column] - row[opponent_column]
    row["REST_DAYS_DIFF"] = home_rest_days - away_rest_days
    features = pd.DataFrame([[row[column] for column in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
    values = features.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise InferenceError("The matchup contains missing or non-finite model features.")
    return features


def _next_team_game_number(
    state: pd.Series,
    history: pd.DataFrame,
    game_date: pd.Timestamp,
) -> int:
    prior = history[
        (history["TEAM_NAME"] == state["TEAM_NAME"])
        & (history["GAME_DATE"] < game_date)
    ]
    if "SEASON" in history.columns and not pd.isna(state.get("SEASON")):
        prior = prior[prior["SEASON"] == state["SEASON"]]
    return int(len(prior) + 1)
