import tempfile
import unittest
from unittest.mock import patch

from src.data_collection.player_data.contracts import parse_utc_text, utc_text
from src.data_collection.player_data.snapshots import SnapshotStore
from src.modeling.player_inference import PlayerContextError, player_context
from tests.test_player_contributions import inputs, GAME, TIME

OBSERVED = '2024-10-10T13:00:00Z'


def context_store(root):
    store = SnapshotStore(root)
    for kind in ('roster', 'statistics', 'availability'):
        document = inputs()[kind]
        moment = parse_utc_text(TIME)
        request = {'team_id':1, 'season':'2024-25', 'season_type':'Regular Season'}
        records = [{**r, 'retrieved_at':utc_text(moment), 'source_url':document['source_url'],
                    'source_as_of':utc_text(moment)} for r in document['records']]
        store.write(provider=document['provider'], dataset=document['dataset'], request=request,
                    source_url=document['source_url'], retrieved_at=moment, source_as_of=moment,
                    records=records, raw_payload={})
    return store


class PlayerInferenceTests(unittest.TestCase):
    def test_scenarios_are_separate_and_official_state_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            store = context_store(root)
            result = player_context(store, team_id=1, game_time=GAME, observed_at=OBSERVED, scenarios={1:.5})
            self.assertIsNone(result['probability_adjustment'])
            self.assertFalse(result['production_features_accepted'])
            self.assertEqual(result['players'][0]['availability'],'out')
            self.assertEqual(result['contribution']['players'][0]['expected_minutes'],15)
            self.assertEqual(result['players'][1]['availability'],'unknown')
            self.assertEqual(result['mode'],'prospective_snapshot_scenario')
            with self.assertRaises(PlayerContextError):
                player_context(store, team_id=1, game_time=GAME, observed_at=OBSERVED, scenarios={1:2})

    def test_stale_reports_do_not_become_current_status(self):
        with tempfile.TemporaryDirectory() as root:
            store = context_store(root)
            result = player_context(store, team_id=1, game_time=GAME, observed_at='2024-10-11T22:00:00Z')
            self.assertEqual(result['players'][0]['reported_status'],'out')
            self.assertEqual(result['players'][0]['availability'],'unknown')
            self.assertEqual(result['contribution']['players'][0]['official_status'],'unknown')
            self.assertTrue(any('Stale official' in w for w in result['warnings']))

    def test_missing_sources_future_snapshots_and_provider_failure(self):
        with tempfile.TemporaryDirectory() as root:
            store = context_store(root)
            result = player_context(store, team_id=1, game_time='2024-10-09T23:00:00Z', observed_at=OBSERVED)
            self.assertEqual(result['players'], [])
            self.assertIsNone(result['contribution'])
            self.assertTrue(any('Missing pregame roster' in w for w in result['warnings']))
            with patch.object(store, 'read', side_effect=OSError('snapshot disk unavailable')), self.assertRaisesRegex(PlayerContextError, 'disk unavailable'):
                player_context(store, team_id=1, game_time=GAME, observed_at=OBSERVED)

    def test_api_player_context_does_not_predict_or_fit(self):
        from src.modeling.inference import InferenceEngine
        engine = InferenceEngine.from_paths()
        with tempfile.TemporaryDirectory() as root, patch.object(engine._model, 'predict_proba', side_effect=AssertionError('prediction')), patch.object(engine._model, 'fit', side_effect=AssertionError('fit')):
            result = engine.player_context('Boston Celtics', store=SnapshotStore(root), game_time='2026-10-10T23:00:00Z', observed_at='2026-10-09T12:00:00Z')
        self.assertIsNone(result['contribution'])
        self.assertEqual(result['players'], [])
