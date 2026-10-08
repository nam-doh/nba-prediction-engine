import unittest
import pandas as pd
from src.modeling.chronological import chronological_split


class ChronologicalTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({'GAME_ID': ['c', 'a', 'b', 'c', 'b', 'a', 'd'],
            'GAME_DATE': ['2024-03-01', '2024-01-01', '2024-02-01',
                          '2024-03-01', '2024-02-01', '2024-01-01', '2024-02-01']})

    def split(self, frame=None, start='2024-02-01', end='2024-03-01'):
        return chronological_split(self.frame if frame is None else frame, start, end)

    def test_boundaries_pairs_and_same_date(self):
        parts = self.split()
        self.assertEqual([set(p.GAME_ID) for p in parts], [{'a'}, {'b', 'd'}, {'c'}])
        self.assertEqual(sum(map(len, parts)), len(self.frame))
        parts[0].iloc[0, 0] = 'changed'
        self.assertNotIn('changed', self.frame.GAME_ID.tolist())

    def test_reversed_or_empty(self):
        for start, end in [('2024-03-01', '2024-02-01'),
                           ('2023-01-01', '2024-03-01'),
                           ('2024-02-01', '2025-01-01')]:
            with self.assertRaises(ValueError):
                self.split(start=start, end=end)

    def test_invalid_missing_and_inconsistent(self):
        for column, value in [('GAME_DATE', 'bad'), ('GAME_DATE', None),
                              ('GAME_ID', None), ('GAME_DATE', '2024-01-02')]:
            frame = self.frame.copy()
            frame.loc[0, column] = value
            with self.assertRaises(ValueError):
                self.split(frame)
