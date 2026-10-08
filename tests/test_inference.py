import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.modeling.inference import (
    DEFAULT_DATA_PATH,
    DEFAULT_MODEL_PATH,
    InferenceEngine,
    InferenceError,
    predict_matchup,
)




class InferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = InferenceEngine.from_paths()
        cls.game_date = cls.engine.data_cutoff + pd.Timedelta(days=1)

    def test_known_matchup_returns_oriented_finite_probabilities_and_metadata(self):
        result = self.engine.predict_matchup(
            "Boston Celtics",
            "Oklahoma City Thunder",
            self.game_date,
            home_rest_days=2,
            away_rest_days=1,
        )

        self.assertGreaterEqual(result.home_win_probability, 0.0)
        self.assertLessEqual(result.home_win_probability, 1.0)
        self.assertAlmostEqual(
            result.home_win_probability + result.away_win_probability,
            1.0,
        )
        self.assertEqual(result.home_team, "Boston Celtics")
        self.assertEqual(result.away_team, "Oklahoma City Thunder")
        self.assertEqual(result.home_rest_days, 2)
        self.assertEqual(result.away_rest_days, 1)
        self.assertEqual(result.feature_count, 36)
        self.assertEqual(result.data_cutoff, self.engine.data_cutoff)
        self.assertLess(result.home_state_date, result.game_date)
        self.assertLess(result.away_state_date, result.game_date)
        self.assertIn("Injuries", result.assumptions["Player availability"])

    def test_one_shot_entry_point_uses_the_persisted_artifact(self):
        result = predict_matchup(
            "Boston Celtics",
            "Oklahoma City Thunder",
            self.game_date,
            2,
            1,
        )
        self.assertEqual(result.model_artifact, DEFAULT_MODEL_PATH.name)

    def test_same_date_and_future_rows_cannot_change_as_of_prediction(self):
        history = pd.read_csv(DEFAULT_DATA_PATH)
        baseline = self.engine.predict_matchup(
            "Boston Celtics",
            "Oklahoma City Thunder",
            self.game_date,
            2,
            1,
        )
        same_date = history[
            history["TEAM_NAME"].isin(["Boston Celtics", "Oklahoma City Thunder"])
        ].sort_values(["TEAM_NAME", "GAME_DATE"]).groupby("TEAM_NAME").tail(1).copy()
        same_date["GAME_DATE"] = self.game_date.strftime("%Y-%m-%d")
        for column in ("SEASON_WIN_PCT", "PTS_ROLL5", "PLUS_MINUS_ROLL5"):
            same_date[column] = 999999.0
        future = same_date.copy()
        future["GAME_DATE"] = "2099-01-01"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.csv"
            pd.concat([history, same_date, future], ignore_index=True).to_csv(path, index=False)
            contaminated_engine = InferenceEngine.from_paths(path, DEFAULT_MODEL_PATH)
            contaminated = contaminated_engine.predict_matchup(
                "Boston Celtics",
                "Oklahoma City Thunder",
                self.game_date,
                2,
                1,
            )

        self.assertEqual(contaminated.home_state_date, baseline.home_state_date)
        self.assertEqual(contaminated.away_state_date, baseline.away_state_date)
        self.assertAlmostEqual(
            contaminated.home_win_probability,
            baseline.home_win_probability,
        )

    def test_invalid_inputs_fail_closed(self):
        cases = (
            ("Boston Celtics", "Boston Celtics", self.game_date, 2, 1, "different"),
            ("Boston Celtics", "Not a Team", self.game_date, 2, 1, "Unknown"),
            ("Boston Celtics", "Oklahoma City Thunder", self.game_date, -1, 1, "rest"),
            ("Boston Celtics", "Oklahoma City Thunder", self.game_date, 2, 15, "rest"),
            ("Boston Celtics", "Oklahoma City Thunder", "not-a-date", 2, 1, "date"),
        )
        for home, away, game_date, home_rest, away_rest, message in cases:
            with self.subTest(message=message), self.assertRaises(InferenceError):
                self.engine.predict_matchup(home, away, game_date, home_rest, away_rest)

    def test_missing_history_and_model_files_are_actionable(self):
        with self.assertRaisesRegex(InferenceError, "Historical feature data was not found"):
            InferenceEngine.from_paths("missing-history.csv", DEFAULT_MODEL_PATH)
        with self.assertRaisesRegex(InferenceError, "Production model was not found"):
            InferenceEngine.from_paths(DEFAULT_DATA_PATH, "missing-model.pkl")

    def test_prediction_does_not_fit_or_mutate_classifier(self):
        classifier = self.engine._model.named_steps["classifier"]
        coefficients_before = classifier.coef_.copy()
        with patch.object(self.engine._model, "fit", side_effect=AssertionError("fit called")):
            self.engine.predict_matchup(
                "Boston Celtics",
                "Oklahoma City Thunder",
                self.game_date,
                2,
                1,
            )
        pd.testing.assert_frame_equal(
            pd.DataFrame(coefficients_before),
            pd.DataFrame(classifier.coef_),
        )


if __name__ == "__main__":
    unittest.main()
