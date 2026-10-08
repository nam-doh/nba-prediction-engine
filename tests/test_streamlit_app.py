import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "dashboards/app.py"


class StreamlitAppTests(unittest.TestCase):
    def _run_app(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=15)
        app.run()
        self.assertFalse(app.exception, "The Streamlit app raised during startup")
        return app

    def test_predicts_known_matchup_and_renders_metadata(self):
        app = self._run_app()
        self.assertGreaterEqual(len(app.selectbox), 2)
        app.selectbox[0].set_value("Boston Celtics")
        app.selectbox[1].set_value("Oklahoma City Thunder")
        app.run()
        app.button[0].click()
        app.run()

        self.assertFalse(app.exception)
        markdown = "\n".join(element.value for element in app.markdown)
        info = "\n".join(element.value for element in app.info)
        self.assertIn("Historical-data prediction", info)
        self.assertIn("Boston Celtics", markdown)
        self.assertIn("Oklahoma City Thunder", markdown)
        self.assertIn("Static team-statistics cutoff", markdown)
        self.assertIn("Production Logistic Regression", markdown)
        self.assertIn("Injuries, lineups, trades", "\n".join(element.value for element in app.warning))
        self.assertTrue(any('class="prob-value"' in element.value for element in app.markdown))

    def test_duplicate_team_selection_shows_error_without_probability(self):
        app = self._run_app()
        app.selectbox[0].set_value("Boston Celtics")
        app.selectbox[1].set_value("Boston Celtics")
        app.run()
        app.button[0].click()
        app.run()

        self.assertFalse(app.exception)
        self.assertTrue(any("two different teams" in element.value for element in app.error))
        markdown = "\n".join(element.value for element in app.markdown)
        self.assertNotIn("Model outlook", markdown)
        self.assertFalse(any('class="prob-value"' in element.value for element in app.markdown))



if __name__ == "__main__":
    unittest.main()
