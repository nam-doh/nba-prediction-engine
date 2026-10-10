"""Read-only, as-of inference over the persisted production pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd

from .pregame_features import REQUIRED, matchup_features, team_state, validate_history


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
            "Historical source": "Static completed-game statistics rebuilt strictly before the game date.",
            "Rest days": "Elapsed calendar days from prior same-season games; explicit overrides are hypothetical scenarios.",
            "Player availability": "Injuries, lineups, trades, and player availability are not modeled.",
            "Probability meaning": "Win probabilities are historical-data estimates, not guarantees.",
        }

    def player_context(self, team: str, *, store, game_time: str, observed_at: str, scenarios=None):
        """Return unvalidated player scenarios separately; never call the classifier."""
        from .player_inference import player_context
        ids = self._history.loc[self._history.TEAM_NAME == team, "TEAM_ID"].unique()
        if len(ids) != 1:
            raise InferenceError("Unknown or ambiguous team identity for player context.")
        return player_context(store, team_id=int(ids[0]), game_time=game_time,
                              observed_at=observed_at, scenarios=scenarios)

    def predict_matchup(
        self,
        home_team: str,
        away_team: str,
        game_date: Any,
        home_rest_days: Any = None,
        away_rest_days: Any = None,
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
        try:
            prior = self._history[self._history.GAME_DATE < game_date]
            year = game_date.year if game_date.month >= 7 else game_date.year - 1
            season = f"{year}-{str(year + 1)[-2:]}"
            home_state = team_state(prior, home_team, game_date, season)
            away_state = team_state(prior, away_team, game_date, season)
            for state in (home_state, away_state):
                if pd.isna(state["GAME_DATE"]):
                    raise ValueError(f"No historical team state for {state['TEAM_NAME']} in {season}")
        except ValueError as exc:
            raise InferenceError(str(exc)) from exc
        home_rest_days = int(home_state["REST_DAYS"]) if home_rest_days is None else _parse_rest_days(home_rest_days, "Home")
        away_rest_days = int(away_state["REST_DAYS"]) if away_rest_days is None else _parse_rest_days(away_rest_days, "Away")
        home_state["REST_DAYS"] = home_rest_days
        away_state["REST_DAYS"] = away_rest_days
        row = matchup_features(home_state, away_state)
        features = pd.DataFrame([[row[c] for c in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
        if not np.isfinite(features.to_numpy(dtype=float)).all():
            raise InferenceError("The matchup contains missing or non-finite model features.")
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



def predict_matchup(
    home_team: str,
    away_team: str,
    game_date: Any,
    home_rest_days: Any = None,
    away_rest_days: Any = None,
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
    missing = sorted(set(REQUIRED).difference(history.columns))
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
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    if not isinstance(model, Pipeline) or tuple(named_steps) != ("scaler", "classifier"):
        raise InferenceError("Expected exactly the persisted scaler/classifier pipeline.")
    scaler, classifier = named_steps["scaler"], named_steps["classifier"]
    if (not isinstance(scaler, StandardScaler) or not isinstance(classifier, LogisticRegression)
            or tuple(getattr(scaler, "feature_names_in_", ())) != FEATURE_COLUMNS
            or getattr(classifier, "n_features_in_", None) != len(FEATURE_COLUMNS)
            or tuple(model.classes_) != (0, 1)):
        raise InferenceError("Invalid scaler/classifier feature or class contract.")
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


