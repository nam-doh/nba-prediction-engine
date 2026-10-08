"""Explicit date partitions without splitting games or evaluating holdout."""
import pandas as pd


def chronological_split(frame, validation_start, holdout_start):
    """Return train, validation, holdout copies using inclusive start cutoffs."""
    dates = pd.to_datetime(frame['GAME_DATE'], errors='raise')
    start, end = pd.Timestamp(validation_start), pd.Timestamp(holdout_start)
    if dates.isna().any() or pd.isna(start) or pd.isna(end) or start >= end:
        raise ValueError('Valid dates and increasing cutoffs are required')
    if frame['GAME_ID'].isna().any():
        raise ValueError('Missing game ID')
    if dates.groupby(frame['GAME_ID']).nunique().gt(1).any():
        raise ValueError('A game has inconsistent dates')
    parts = tuple(frame.loc[mask].copy() for mask in
                  (dates < start, (dates >= start) & (dates < end), dates >= end))
    if any(part.empty for part in parts):
        raise ValueError('Every partition must contain games')
    return parts
