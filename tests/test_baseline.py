import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from scripts.baseline import FEATURES, candidate_passes, evaluate, prepare


def fixture():
    rows = []
    for game, date, level in [('a', '2022-01-01', 0), ('b', '2023-01-01', 2),
                              ('c', '2024-10-22', 100), ('d', '2024-10-22', 200),
                              ('e', '2025-10-21', 1000), ('f', '2026-10-20', 2000)]:
        for team in (1, 2):
            rows.append(dict(GAME_ID=game, GAME_DATE=date, TEAM_ID=team,
                             WIN=team - 1, **{f: level + team for f in FEATURES}))
    return pd.DataFrame(rows).astype({f: float for f in FEATURES}).sample(frac=1, random_state=7).reset_index(drop=True)


class BaselineTests(unittest.TestCase):
    def test_train_only_scaler_and_untouched_input(self):
        data = fixture()
        original = data.copy(deep=True)
        report, model = evaluate(data)
        train, validation = prepare(data)[0]
        np.testing.assert_allclose(model['scaler'].mean_, train.loc[:, FEATURES].mean())
        self.assertEqual(model['scaler'].n_samples_seen_, 4)
        self.assertEqual(len(validation), 4)
        self.assertEqual(report['counts']['excluded_rows'], 4)
        self.assertEqual(set(report['metrics']), {'accuracy', 'roc_auc', 'log_loss', 'brier'})
        assert_frame_equal(data, original)

    def test_exposed_and_future_values_never_affect_fit_or_scores(self):
        data = fixture()
        first, _ = evaluate(data)
        excluded = data['GAME_DATE'] >= '2025-07-01'
        data.loc[excluded, list(FEATURES)] = np.inf
        data.loc[excluded, 'WIN'] = 99
        second, _ = evaluate(data)
        self.assertEqual(first, second)

    def test_pair_filtering_and_same_date_partition(self):
        data = fixture()
        data.loc[(data.GAME_ID == 'c') & (data.TEAM_ID == 1), FEATURES[0]] = np.nan
        (train, validation), counts = prepare(data)
        self.assertEqual(set(validation.GAME_ID), {'d'})
        self.assertEqual(counts['incomplete_rows_removed'], 2)
        self.assertLess(train.GAME_DATE.max(), validation.GAME_DATE.min())

    def test_invalid_inputs_fail_closed(self):
        for column, value in [('GAME_DATE', 'bad'), ('GAME_ID', None),
                              ('TEAM_ID', None), ('WIN', 3), (FEATURES[0], np.inf)]:
            with self.subTest(column=column):
                data = fixture()
                idx = data.index[data.GAME_ID == 'a'][0]
                data.loc[idx, column] = value
                with self.assertRaises((ValueError, TypeError)):
                    prepare(data)
        data = fixture()
        with self.assertRaises(ValueError):
            prepare(data.loc[data.GAME_ID != 'a'].iloc[1:])
        with self.assertRaises(ValueError):
            prepare(data.loc[data.GAME_DATE >= '2024-07-01'])

    def test_frozen_gates(self):
        base = dict(log_loss=0.6, brier=0.2, roc_auc=0.7)
        good = dict(log_loss=0.59, brier=0.2, roc_auc=0.695)
        self.assertTrue(candidate_passes(base, good))
        for key, value in [('log_loss', 0.6), ('brier', 0.201),
                           ('roc_auc', 0.6949), ('log_loss', float('nan'))]:
            self.assertFalse(candidate_passes(base, good | {key: value}))
        self.assertFalse(candidate_passes(base, base))


if __name__ == '__main__':
    unittest.main()
