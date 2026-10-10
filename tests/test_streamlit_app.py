import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.data_collection.player_data.contracts import utc_text
from src.data_collection.player_data.snapshots import SnapshotStore
from src.modeling.inference import InferenceEngine

APP_PATH = Path(__file__).resolve().parents[1] / "dashboards/app.py"


class StreamlitAppTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        environment = patch.dict('os.environ', {'NBA_PLAYER_SNAPSHOT_DIR': directory.name})
        environment.start()
        self.addCleanup(environment.stop)

    def _populate_player_snapshots(self, teams):
        store = SnapshotStore(self.snapshot_dir)
        now = datetime.now(timezone.utc) - timedelta(minutes=2)
        game_day = now.date() + timedelta(days=1)
        season = f"{game_day.year}-{str(game_day.year + 1)[-2:]}" if game_day.month >= 7 else f"{game_day.year-1}-{str(game_day.year)[-2:]}"
        engine = InferenceEngine.from_paths()
        team_ids = {team: int(engine._history.loc[engine._history.TEAM_NAME == team, 'TEAM_ID'].iloc[0]) for team in teams}
        for index, team in enumerate(teams):
            team_id = team_ids[team]
            player_id = 900000 + index
            request = {'team_id': team_id, 'season': season}
            source_url = 'https://example.org/local-fixture'
            roster_time = now - timedelta(minutes=1)
            store.write(provider='nba_stats', dataset='team_rosters', request=request, source_url=source_url,
                        retrieved_at=roster_time, source_as_of=roster_time, raw_payload={},
                        records=[dict(team_id=team_id, player_id=player_id, player_name=f'Fixture {index}',
                                      position='G', season=season, source_url=source_url, retrieved_at=utc_text(roster_time))])
            store.write(provider='nba_stats', dataset='player_game_logs',
                        request={**request, 'season_type':'Regular Season'}, source_url=source_url,
                        retrieved_at=roster_time, source_as_of=roster_time, raw_payload={},
                        records=[dict(team_id=team_ids[other], player_id=900000+other_index,
                                      player_name=f'Fixture {other_index}', game_id=f'fixture-{other_index}',
                                      game_date=(game_day-timedelta(days=1)).isoformat(), season=season,
                                      minutes=30, points=20, rebounds=4, assists=5, steals=1, blocks=1,
                                      turnovers=2, source_url=source_url, retrieved_at=utc_text(roster_time))
                                 for other_index, other in enumerate(teams)])
            report_time = now - timedelta(minutes=1)
            store.write(provider='nba_official', dataset='availability',
                        request={'fixture':index}, source_url='https://example.org/local-report',
                        retrieved_at=report_time, source_as_of=report_time, raw_payload={},
                        records=[dict(team_id=team_id, player_id=player_id, game_date=game_day.isoformat(),
                                      status='out', reason='fixture only', source_url='https://example.org/local-report',
                                      source_as_of=utc_text(report_time), retrieved_at=utc_text(report_time))])
            news_time = now - timedelta(seconds=30)
            store.write(provider='gnews', dataset='player_news', request={'player_id':player_id},
                        source_url='https://gnews.io/api/v4/search', retrieved_at=news_time, raw_payload={},
                        records=[dict(player_id=player_id, player_name=f'Fixture {index}', headline='Fixture availability story',
                                      published_at=utc_text(news_time), retrieved_at=utc_text(news_time),
                                      source_url='https://example.org/article', supporting_text='Fixture report text.',
                                      reported_availability=None, official=False)])

    @property
    def snapshot_dir(self):
        import os
        return Path(os.environ['NBA_PLAYER_SNAPSHOT_DIR'])

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

    def test_player_panel_is_separate_from_production_prediction(self):
        app = self._run_app()
        self.assertTrue(any("Scenario analysis only" in e.value for e in app.info))
        self.assertTrue(any("missing does not mean available" in e.value for e in app.warning))
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('class="prob-value"' in e.value for e in app.markdown))
        self.assertTrue(any("do not change the production probabilities" in e.value for e in app.info))

    def test_live_snapshot_scenarios_render_beside_unchanged_probabilities(self):
        teams = ("Atlanta Hawks", "Boston Celtics")
        self._populate_player_snapshots(teams)
        app = self._run_app()
        self.assertFalse(app.exception)
        tables = [element.value for element in app.dataframe]
        self.assertEqual(len(tables), 4, [e.value for e in app.error])
        for roster, rotation in zip(tables[::2], tables[1::2]):
            self.assertEqual(roster.loc[0, "reported_status"], "out")
            self.assertEqual(roster.loc[0, "availability"], "out")
            self.assertEqual(rotation.loc[0, "official_status"], "out")
        self.assertTrue(any("UNCONFIRMED" in e.value for e in app.caption))
        self.assertTrue(any("Source-as-of:" in e.value for e in app.caption))
        app.button[0].click().run()
        self.assertFalse(app.exception)
        after = [e.value for e in app.markdown if 'class="prob-value"' in e.value]
        self.assertEqual(len(after), 2)



if __name__ == "__main__":
    unittest.main()
