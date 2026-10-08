import hashlib
import json
import unittest

import numpy as np
import pandas as pd

from scripts.baseline import FEATURES
from scripts.evaluation_report import PROTOCOL_ID, render, report_from_bytes


def fixture():
    rows = []
    games = [
        ('a', '2022-01-01', 0),
        ('b', '2023-01-01', 10),
        ('c', '2024-10-22', 20),
        ('d', '2024-10-23', 30),
        ('exposed', '2025-10-21', 40),
        ('future', '2026-10-20', 50),
    ]
    for game, date, level in games:
        for team in (1, 2):
            rows.append(
                dict(
                    GAME_ID=game,
                    GAME_DATE=date,
                    TEAM_ID=team,
                    WIN=team - 1,
                    **{feature: level + team for feature in FEATURES},
                )
            )
    return pd.DataFrame(rows).astype({feature: float for feature in FEATURES})


class EvaluationReportTests(unittest.TestCase):
    def test_repeated_snapshot_is_byte_identical_and_complete(self):
        payload = fixture().to_csv(index=False).encode()
        first = render(report_from_bytes(payload))
        second = render(report_from_bytes(payload))
        self.assertEqual(first, second)

        report = json.loads(first)
        self.assertEqual(report['protocol_id'], PROTOCOL_ID)
        self.assertEqual(report['data_sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(report['features'], list(FEATURES))
        self.assertEqual(report['feature_sha256'], '24381691fe6584c9c3999fc70329fb2abfd03e4be0582a2ead0be99d5f66e3ed')
        self.assertEqual(report['seed'], 42)
        self.assertEqual(set(report['metrics']), {'accuracy', 'roc_auc', 'log_loss', 'brier'})
        self.assertEqual(report['partitions']['train']['rows'], 4)
        self.assertEqual(report['partitions']['train']['games'], 2)
        self.assertEqual(report['partitions']['validation']['rows'], 4)
        self.assertEqual(report['partitions']['validation']['games'], 2)
        self.assertEqual(report['partitions']['validation']['interval']['end'], '2025-07-01')
        self.assertEqual(report['versions']['python'].split('.')[0], '3')

    def test_exposed_and_future_rows_are_not_evaluated(self):
        original = fixture()
        first = report_from_bytes(original.to_csv(index=False).encode())
        changed = original.copy()
        exposed = changed['GAME_DATE'] >= '2025-07-01'
        changed.loc[exposed, FEATURES[0]] = np.inf
        changed.loc[exposed, 'WIN'] = 99
        second = report_from_bytes(changed.to_csv(index=False).encode())
        self.assertEqual(first['metrics'], second['metrics'])
        self.assertEqual(first['partitions'], second['partitions'])

    def test_invalid_inputs_and_mixed_partitions_fail_closed(self):
        cases = []
        invalid_date = fixture()
        invalid_date.loc[0, 'GAME_DATE'] = 'not-a-date'
        cases.append(invalid_date)

        missing_id = fixture()
        missing_id.loc[0, 'TEAM_ID'] = None
        cases.append(missing_id)

        missing_feature = fixture().drop(columns=[FEATURES[0]])
        cases.append(missing_feature)

        mixed = fixture()
        mixed.loc[mixed['GAME_ID'] == 'a', 'GAME_DATE'] = ['2022-01-01', '2024-10-22']
        cases.append(mixed)

        for data in cases:
            with self.subTest(data=data):
                with self.assertRaises((ValueError, TypeError, KeyError)):
                    report_from_bytes(data.to_csv(index=False).encode())

    def test_source_payload_is_not_mutated(self):
        data = fixture()
        payload = data.to_csv(index=False).encode()
        before = payload[:]
        report_from_bytes(payload)
        self.assertEqual(payload, before)


if __name__ == '__main__':
    unittest.main()
