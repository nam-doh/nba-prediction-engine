import hashlib
import json
import unittest

import numpy as np
import pandas as pd

from scripts.baseline import FEATURES
from scripts.reliability import (
    CALIBRATION_BIN_EDGES,
    calibration_bins,
    probability_summary,
    render,
    report_from_bytes,
)


def fixture():
    rows = []
    games = [
        ('a', '2022-01-01', 0),
        ('b', '2023-01-01', 10),
        ('c', '2024-10-22', 20),
        ('d', '2024-10-22', 30),
        ('exposed', '2025-10-21', 40),
        ('future', '2026-10-20', 50),
    ]
    for game, date, level in games:
        for team in (1, 2):
            rows.append(dict(
                GAME_ID=game,
                GAME_DATE=date,
                TEAM_ID=team,
                WIN=team - 1,
                **{feature: level + team for feature in FEATURES},
            ))
    return pd.DataFrame(rows).astype({feature: float for feature in FEATURES})


class ReliabilityTests(unittest.TestCase):
    def test_report_is_deterministic_and_contains_validation_reliability(self):
        payload = fixture().to_csv(index=False).encode()
        first = render(report_from_bytes(payload))
        second = render(report_from_bytes(payload))
        self.assertEqual(first, second)

        report = json.loads(first)
        self.assertEqual(report['data_sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(report['protocol_id'], 'T003-v1')
        self.assertEqual(
            set(report['metrics']), {'accuracy', 'roc_auc', 'log_loss', 'brier'}
        )
        validation = report['partitions']['validation']
        self.assertEqual(validation['sample_count'], 4)
        self.assertEqual(validation['class_counts'], {'0': 2, '1': 2})
        self.assertEqual(validation['class_prevalence'], 0.5)
        self.assertEqual(report['preprocessing']['fit_partition'], 'train')
        self.assertEqual(report['preprocessing']['scored_partition'], 'validation')
        self.assertEqual(
            report['calibration']['bin_edges'], list(CALIBRATION_BIN_EDGES)
        )
        self.assertEqual(
            sum(bin_data['count'] for bin_data in report['calibration']['bins']),
            validation['sample_count'],
        )

    def test_exposed_and_future_rows_cannot_contaminate_report(self):
        original = fixture()
        first = report_from_bytes(original.to_csv(index=False).encode())
        changed = original.copy()
        excluded = changed['GAME_DATE'] >= '2025-07-01'
        changed.loc[excluded, list(FEATURES)] = np.inf
        changed.loc[excluded, 'WIN'] = 99
        second = report_from_bytes(changed.to_csv(index=False).encode())
        self.assertEqual(first | {'data_sha256': None}, second | {'data_sha256': None})

    def test_same_date_games_stay_in_validation(self):
        report = report_from_bytes(fixture().to_csv(index=False).encode())
        self.assertEqual(report['partitions']['validation']['games'], 2)
        self.assertEqual(report['partitions']['validation']['first_date'], '2024-10-22')
        self.assertEqual(report['partitions']['validation']['last_date'], '2024-10-22')

    def test_calibration_bins_are_fixed_and_repeatable(self):
        target = np.array([0, 1] * 5)
        probabilities = np.array([0.0, 0.1, 0.2, 0.3, 0.4,
                                  0.5, 0.6, 0.7, 0.8, 1.0])
        first = calibration_bins(target, probabilities)
        second = calibration_bins(target, probabilities)
        self.assertEqual(first, second)
        self.assertEqual([entry['count'] for entry in first], [1] * 10)
        self.assertEqual(first[0]['lower'], 0.0)
        self.assertEqual(first[-1]['upper'], 1.0)

    def test_missing_or_invalid_probabilities_fail_closed(self):
        with self.assertRaises(ValueError):
            probability_summary([0, 1], [0.4, np.nan])
        with self.assertRaises(ValueError):
            probability_summary([0, 1], [0.4, 1.1])

    def test_incomplete_game_pair_fails_closed(self):
        incomplete = fixture().drop(index=fixture().index[fixture()['GAME_ID'] == 'c'][0])
        with self.assertRaises(ValueError):
            report_from_bytes(incomplete.to_csv(index=False).encode())


if __name__ == '__main__':
    unittest.main()
