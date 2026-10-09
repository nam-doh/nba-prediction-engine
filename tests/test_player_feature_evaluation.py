from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from scripts.player_feature_evaluation import evaluate_players
from src.data_collection.player_data.contracts import ValidationError, utc_text
from src.data_collection.player_data.snapshots import SnapshotStore
from tests.test_baseline import fixture


def archive_fixture(root):
    store = SnapshotStore(root)
    manifest = []
    frame = fixture()
    for row in frame[frame.GAME_DATE < '2025-07-01'].itertuples():
        game = datetime.fromisoformat(row.GAME_DATE).replace(tzinfo=timezone.utc)
        retrieved = game - timedelta(hours=12)
        year = game.year if game.month >= 7 else game.year-1
        season = f'{year}-{str(year+1)[-2:]}'
        prior_date = (game-timedelta(days=2)).date().isoformat()
        entry = dict(game_id=row.GAME_ID, team_id=row.TEAM_ID)
        for kind, dataset, provider, records in (
            ('roster', 'team_rosters', 'nba_stats', [dict(player_id=1, team_id=row.TEAM_ID, player_name='Example Player', position='G', season=season)]),
            ('statistics', 'player_game_logs', 'nba_stats', [dict(player_id=1, team_id=row.TEAM_ID, game_id='prior', game_date=prior_date, season=season,
                minutes=30, points=20, rebounds=4, assists=5, steals=1, blocks=1, turnovers=2)]),
            ('availability', 'availability', 'nba_official', [dict(player_id=1, team_id=row.TEAM_ID, game_date=row.GAME_DATE, status='out')])):
            path = store.write(provider=provider, dataset=dataset, request=entry.copy(), source_url='https://example.org/snapshot',
                               retrieved_at=retrieved, source_as_of=retrieved,
                               records=[dict(r, retrieved_at=utc_text(retrieved)) for r in records], raw_payload={})
            entry[kind] = str(path.relative_to(store.root))
        manifest.append(entry)
    return frame, manifest, store


class PlayerEvaluationTests(unittest.TestCase):
    def test_missing_coverage_blocks_candidate_not_fabricated(self):
        with tempfile.TemporaryDirectory() as root:
            result = evaluate_players(fixture().to_csv(index=False).encode(), [], SnapshotStore(root))
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['candidates'], {})
        self.assertIn('8 retained', result['blockers'][0])
        self.assertFalse(result['production_promoted'])

    def test_chronological_comparison_and_holdout_exclusion(self):
        with tempfile.TemporaryDirectory() as root:
            frame, manifest, store = archive_fixture(root)
            first = evaluate_players(frame.to_csv(index=False).encode(), manifest, store)
            self.assertEqual(first['status'], 'evaluated_not_promoted')
            self.assertEqual(set(first['candidates']), {'player_statistics','availability_scenarios'})
            for candidate in first['candidates'].values():
                self.assertEqual(candidate['sample_count'], 4)
                self.assertEqual(candidate['train_rows'], 4)
                self.assertEqual(sum(b['count'] for b in candidate['calibration']['bins']),4)
            frame.loc[frame.GAME_DATE >= '2025-07-01', 'WIN'] = 99
            manifest.append(dict(game_id='f', team_id=1, roster='unread-holdout-file'))
            second = evaluate_players(frame.to_csv(index=False).encode(), manifest, store)
            self.assertEqual(first['candidates'], second['candidates'])
            self.assertEqual(first['baseline'], second['baseline'])
            self.assertEqual(second['accepted_features'], [])

    def test_late_roster_and_missing_availability(self):
        with tempfile.TemporaryDirectory() as root:
            frame, manifest, store = archive_fixture(root)
            manifest[0].pop('availability')
            result = evaluate_players(frame.to_csv(index=False).encode(), manifest, store)
            self.assertEqual(set(result['candidates']), {'player_statistics'})
            self.assertEqual(result['status'], 'blocked')
            # Later-season roster cannot be replayed against an earlier development game.
            older = next(e for e in manifest if e['game_id']=='a')
            newer = next(e for e in manifest if e['game_id']=='c')
            older['roster'] = newer['roster']
            with self.assertRaises(ValidationError):
                evaluate_players(frame.to_csv(index=False).encode(), manifest, store)
