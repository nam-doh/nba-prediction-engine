import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from src.data_collection.player_data.contracts import parse_utc_text, utc_text
from tests.test_player_inference import context_store, OBSERVED, TIME


def panel_app(root, observed):
    from types import SimpleNamespace
    from dashboards.player_panels import render_team_panel
    from src.modeling.player_inference import player_context
    from src.data_collection.player_data.snapshots import SnapshotStore
    engine = SimpleNamespace(player_context=lambda team, **kwargs: player_context(team_id=1, **kwargs))
    render_team_panel(engine, 'Synthetic team', store=SnapshotStore(root),
                      game_time='2024-10-11T23:00:00Z', observed_at=observed, key='test')


class PlayerPanelTests(unittest.TestCase):
    def test_complete_state_provenance_news_and_scenario_override(self):
        with tempfile.TemporaryDirectory() as root:
            store = context_store(root)
            moment = parse_utc_text(TIME)
            store.write(provider='gnews', dataset='player_news', request={'player_id':1},
                        source_url='https://gnews.io/api/v4/search', retrieved_at=moment, raw_payload={},
                        records=[dict(player_id=1, player_name='Player 1', headline='Player 1 update',
                                      published_at=utc_text(moment), retrieved_at=utc_text(moment), source_url='https://example.org/news',
                                      supporting_text='Player 1 is listed as questionable.', reported_availability='questionable', official=False)])
            app = AppTest.from_function(panel_app, args=(root, OBSERVED)).run()
            self.assertFalse(app.exception)
            table = app.dataframe[0].value
            self.assertEqual(table.loc[0,'availability'],'out')
            self.assertEqual(table.loc[1,'availability'],'unknown')
            self.assertTrue(any('UNCONFIRMED' in c.value for c in app.caption))
            self.assertTrue(any('Source-as-of:' in c.value for c in app.caption))
            app.selectbox[0].set_value(1).run()
            app.number_input[0].set_value(.5).run()
            self.assertFalse(app.exception)
            contributions = app.dataframe[1].value
            self.assertEqual(contributions.loc[0,'expected_minutes'],15.)
            self.assertEqual(contributions.loc[0,'official_status'],'out')

    def test_stale_state_keeps_claim_separate_from_unknown(self):
        with tempfile.TemporaryDirectory() as root:
            context_store(root)
            app = AppTest.from_function(panel_app, args=(root, '2024-10-11T22:00:00Z')).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.dataframe[0].value.loc[0,'reported_status'],'out')
            self.assertEqual(app.dataframe[0].value.loc[0,'availability'],'unknown')
            self.assertTrue(any('Stale official' in w.value for w in app.warning))

    def test_missing_and_failed_sources_render_no_fabricated_contributions(self):
        with tempfile.TemporaryDirectory() as root:
            app = AppTest.from_function(panel_app, args=(root, OBSERVED)).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.dataframe),0)
            self.assertTrue(any('Missing pregame roster' in w.value for w in app.warning))
            context_store(root)
            with patch('src.data_collection.player_data.snapshots.SnapshotStore.read', side_effect=OSError('disk failure')):
                app = AppTest.from_function(panel_app, args=(root, OBSERVED)).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('disk failure' in e.value for e in app.error))
            self.assertEqual(len(app.dataframe),0)
