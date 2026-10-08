import copy
import csv
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from scripts.audit_leakage import (DIFFERENCES, OPPONENT, STATS,
                                   audit_rows, main)


def fixture():
    history, modeling = [], []
    # Independently specified expectations: square-valued box scores and
    # alternating wins; seventh game verifies the five-game window cutoff.
    means = (None, 1, 2.5, 14 / 3, 7.5, 11, 18)
    win_means = (None, 1, .5, 2 / 3, .5, .6, .4)
    for season in ('2023-24', '2024-25'):
        for i in range(1, 8):
            for team in ('A', 'B'):
                win = i % 2 if team == 'A' else 1 - i % 2
                row = {'SEASON': season, 'GAME_ID': f'{season}-{i:02}',
                       'TEAM_ID': team, 'GAME_DATE': f'{season[:4]}-11-{i:02}',
                       'WIN': win, **{c: i * i for c in STATS}}
                history.append(row)
                n = i - 1
                prev_wins = (n + 1) // 2 if team == 'A' else n // 2
                vals = {f'{c}_ROLL5': means[n] for c in STATS}
                vals['WIN_PCT_ROLL5'] = (win_means[n] if team == 'A' else
                                        1 - win_means[n]) if n else None
                vals.update(PREV_WIN=1 - win if n else None,
                            PREV_PTS=n * n if n else None,
                            PREV_WINS=prev_wins, PREV_GAMES=n,
                            SEASON_WIN_PCT=prev_wins / n if n else None,
                            TEAM_GAME_NUMBER=i, REST_DAYS=1 if n else None,
                            WIN_STREAK=1 - win if n else 0)
                modeling.append(row | vals | {'OPPONENT_TEAM_ID': 'B' if team == 'A' else 'A'})
    for i in range(0, len(modeling), 2):
        a, b = modeling[i:i + 2]
        for row, opp in ((a, b), (b, a)):
            row.update({f'OPP_{c}': opp[c] for c in OPPONENT})
            for c in DIFFERENCES:
                row[f'{c}_DIFF'] = row[c] - opp[c] if row[c] is not None else None
    return history, modeling


class LeakageAuditTests(unittest.TestCase):
    def setUp(self):
        self.history, self.modeling = fixture()

    def test_unsorted_valid_season_reset_window_and_read_only(self):
        self.history.reverse()
        self.modeling.reverse()
        before = copy.deepcopy((self.history, self.modeling))
        report = audit_rows(self.history, self.modeling)
        self.assertTrue(report['ok'], report)
        self.assertEqual(report['checks']['PTS_ROLL5'], 28)
        self.assertEqual((self.history, self.modeling), before)

    def test_current_game_contamination(self):
        self.modeling[2]['PTS_ROLL5'] = 2.5  # Includes current 4 instead of prior 1.
        report = audit_rows(self.history, self.modeling)
        self.assertFalse(report['ok'])
        self.assertEqual(report['issues'], {'feature_mismatch': 1})
        self.assertEqual(report['samples'][0]['column'], 'PTS_ROLL5')

    def test_cumulative_opponent_difference_and_missingness_contamination(self):
        for column, value in (('PREV_WINS', 2), ('SEASON_WIN_PCT', 1),
                              ('OPP_PTS_ROLL5', 99), ('PTS_ROLL5_DIFF', 99),
                              ('PTS_ROLL5', None), ('PTS_ROLL5', 'inf')):
            with self.subTest(column=column, value=value):
                rows = copy.deepcopy(self.modeling)
                rows[4][column] = value
                self.assertFalse(audit_rows(self.history, rows)['ok'])
        self.modeling[0]['PTS_ROLL5'] = 0
        self.assertFalse(audit_rows(self.history, self.modeling)['ok'])

    def test_cardinality_identity_and_coverage(self):
        for operation in ('duplicate', 'missing', 'wrong_opponent'):
            with self.subTest(operation=operation):
                rows = copy.deepcopy(self.modeling)
                if operation == 'duplicate':
                    rows.append(rows[0].copy())
                elif operation == 'missing':
                    rows.pop()
                else:
                    rows[0]['OPPONENT_TEAM_ID'] = 'A'
                self.assertFalse(audit_rows(self.history, rows)['ok'])

    def test_temporal_and_schema_failures(self):
        for operation in ('invalid_date', 'same_date', 'inconsistent_date',
                          'missing_column', 'missing_id', 'null_id', 'invalid_win'):
            with self.subTest(operation=operation):
                rows = copy.deepcopy(self.history)
                if operation == 'invalid_date':
                    rows[0]['GAME_DATE'] = 'bad'
                elif operation == 'same_date':
                    rows[2]['GAME_DATE'] = rows[3]['GAME_DATE'] = rows[0]['GAME_DATE']
                elif operation == 'inconsistent_date':
                    rows[0]['GAME_DATE'] = '2023-10-31'
                elif operation == 'missing_column':
                    del rows[0]['PTS']
                elif operation in ('missing_id', 'null_id'):
                    rows[0]['TEAM_ID'] = '' if operation == 'missing_id' else None
                else:
                    rows[0]['WIN'] = 2
                self.assertFalse(audit_rows(rows, self.modeling)['ok'])
        self.assertFalse(audit_rows([], [])['ok'])

    def test_exported_date_must_match_source(self):
        for row in self.modeling[:2]:
            row['GAME_DATE'] = '2023-10-31'
        self.assertIn('source_date_mismatch', audit_rows(self.history, self.modeling)['issues'])

    def test_cli_read_only_and_failure_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ('history.csv', 'modeling.csv')]
            for path, rows in zip(paths, (self.history, self.modeling)):
                with path.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
            before = [p.read_bytes() for p in paths]
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(['--history', str(paths[0]), '--modeling', str(paths[1])]), 0)
            self.assertTrue(json.loads(output.getvalue())['ok'])
            self.assertEqual([p.read_bytes() for p in paths], before)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--history', str(Path(folder) / 'absent.csv')]), 1)
