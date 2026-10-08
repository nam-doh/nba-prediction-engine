import unittest
import pandas as pd
from src.modeling.pregame_features import STATS, build_pregame_features, team_state, validate_history


def history():
    rows = []
    for game, date, season in [(1, '2024-10-01', '2024-25'), (2, '2024-10-03', '2024-25'),
                               (3, '2024-10-03', '2024-25'), (4, '2025-10-01', '2025-26')]:
        for team in (1, 2):
            rows.append(dict(SEASON=season, GAME_ID=game, GAME_DATE=date, TEAM_ID=team,
                             TEAM_NAME=str(team), WIN=team-1, **{s: game * 10 + team for s in STATS}))
    return pd.DataFrame(rows)


class PregameTests(unittest.TestCase):
    def test_prior_only_same_date_and_season_reset(self):
        result = build_pregame_features(history()).set_index(['GAME_ID', 'TEAM_ID'])
        self.assertEqual(result.loc[(2, 1), 'PTS_ROLL5'], 11)
        self.assertEqual(result.loc[(3, 1), 'PTS_ROLL5'], 11)
        self.assertEqual(result.loc[(3, 1), 'OPP_PTS_ROLL5'], 12)
        self.assertEqual(result.loc[(3, 1), 'REST_DAYS'], 2)
        self.assertEqual(result.loc[(3, 1), 'TEAM_GAME_NUMBER'], 2)
        self.assertTrue(pd.isna(result.loc[(4, 1), 'PTS_ROLL5']))
        self.assertEqual(result.loc[(4, 1), 'TEAM_GAME_NUMBER'], 1)

    def test_current_future_statistics_cannot_contaminate(self):
        source = history()
        before = build_pregame_features(source)
        source.loc[source.GAME_ID >= 2, list(STATS)] = 9999
        after = build_pregame_features(source)
        pd.testing.assert_frame_equal(before, after)

    def test_bad_pairs_order_and_missing_fields_fail(self):
        source = history()
        for bad in (source.iloc[1:], pd.concat([source, source.iloc[:1]]),
                    source.iloc[::-1], source.drop(columns='PTS'),
                    source.assign(OPPONENT_TEAM_ID=999)):
            with self.subTest(), self.assertRaises(ValueError):
                build_pregame_features(bad)

    def test_state_uses_last_completed_game_not_stale_export(self):
        state = team_state(validate_history(history()), '1', '2024-10-04', '2024-25')
        self.assertEqual(state['PTS_ROLL5'], 21)
        self.assertEqual(state['TEAM_GAME_NUMBER'], 4)
        self.assertEqual(state['REST_DAYS'], 1)
