import copy
import unittest
from src.data_collection.player_data.contracts import ValidationError
from src.modeling.player_contributions import estimate_contributions

TIME = '2024-10-10T12:00:00Z'
GAME = '2024-10-11T23:00:00Z'


def inputs():
    def snapshot(dataset, records, provider='nba_stats'):
        return dict(provider=provider, dataset=dataset, retrieved_at=TIME, source_as_of=None,
                    source_url='https://example.org/source', records=[dict(r, retrieved_at=TIME) for r in records])
    roster = snapshot('team_rosters', [dict(player_id=p, team_id=1, player_name=f'Player {p}', position=role, season='2024-25')
                                     for p,role in ((1,'G'),(2,'G'),(3,'C'))])
    logs = [dict(player_id=p, team_id=1, game_id=str(g), game_date=f'2024-10-0{g}', season='2024-25',
                 minutes=30, points=p*10, rebounds=3, assists=4, steals=1, blocks=1, turnovers=2)
            for g in (1,2,3) for p in (1,2,3)]
    statistics = snapshot('player_game_logs', logs)
    availability = snapshot('availability', [dict(player_id=1, team_id=1, game_date='2024-10-11', status='out')], 'nba_official')
    return dict(roster=roster, statistics=statistics, availability=availability, team_id=1, game_time=GAME)


class ContributionTests(unittest.TestCase):
    def test_role_redistribution_caps_and_unknown(self):
        result = estimate_contributions(**inputs())
        first, second, center = result['players']
        self.assertEqual(first['expected_minutes'], 0)
        self.assertEqual(second['expected_minutes'], 42)
        self.assertEqual(center['expected_minutes'], 30)
        self.assertEqual(second['official_status'], 'unknown')
        self.assertTrue(second['availability_uncertain'])
        self.assertEqual(result['unallocated_minutes'], 18)
        self.assertEqual(result['features']['unavailable_minutes_fraction'], 30/240)
        self.assertNotEqual(result['features']['rotation_strength_delta'], 0)

    def test_same_date_future_and_future_roster(self):
        args = inputs()
        before = estimate_contributions(**args)
        future = dict(args['statistics']['records'][0], game_id='future', game_date='2024-10-11', points=999999)
        args['statistics']['records'].append(future)
        self.assertEqual(estimate_contributions(**args), before)
        args['roster']['retrieved_at'] = '2024-10-12T00:00:00Z'
        with self.assertRaises(ValidationError):
            estimate_contributions(**args)

    def test_explicit_scenarios_do_not_relabel_official_or_mutate(self):
        args = inputs()
        original = copy.deepcopy(args)
        result = estimate_contributions(**args, scenarios={1:1})
        self.assertEqual(result['players'][0]['official_status'], 'out')
        self.assertEqual(result['players'][0]['expected_minutes'], 30)
        self.assertEqual(result['features']['rotation_strength_delta'], 0)
        self.assertEqual(args, original)
        for scenarios in ({999:0}, {1:-1}, {1:1.1}, {1:float('nan')}):
            with self.assertRaises(ValidationError):
                estimate_contributions(**args, scenarios=scenarios)

    def test_shrinkage_missing_availability_and_duplicate_games(self):
        args = inputs()
        args['availability'] = None
        result = estimate_contributions(**args)
        self.assertTrue(all(p['official_status']=='unknown' for p in result['players']))
        self.assertEqual(result['features']['rotation_strength_delta'], 0)
        # Raw strengths differ by 2/3 per minute; shrinkage reduces their separation.
        strengths = [p['strength'] for p in result['players']]
        self.assertLess(strengths[2]-strengths[0], 2/3)
        args['statistics']['records'].append(dict(args['statistics']['records'][0]))
        with self.assertRaises(ValidationError):
            estimate_contributions(**args)

    def test_invalid_provenance_and_late_official_report(self):
        for dataset in ('roster','statistics','availability'):
            args = inputs()
            args[dataset]['source_as_of'] = GAME
            with self.assertRaises(ValidationError):
                estimate_contributions(**args)
