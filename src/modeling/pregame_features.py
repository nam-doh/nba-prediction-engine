"""Strict date-as-of features from completed games, never exported pregame values."""
from __future__ import annotations

import numpy as np
import pandas as pd

STATS = ('PTS', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PLUS_MINUS')
ROLLING = {f'{s}_ROLL5': s for s in STATS} | {'WIN_PCT_ROLL5': 'WIN'}
DIFFERENCES = ('PTS_ROLL5', 'FG_PCT_ROLL5', 'FG3_PCT_ROLL5', 'REB_ROLL5',
               'AST_ROLL5', 'TOV_ROLL5', 'PLUS_MINUS_ROLL5', 'WIN_PCT_ROLL5', 'REST_DAYS')
REQUIRED = ('SEASON', 'GAME_ID', 'TEAM_ID', 'TEAM_NAME', 'GAME_DATE', 'WIN', *STATS)


def game_date(value):
    date = pd.Timestamp(value)
    if pd.isna(date) or date.tz is not None or date != date.normalize():
        raise ValueError('game_date must be a timezone-free calendar date')
    return date


def validate_history(history):
    missing = set(REQUIRED) - set(history.columns)
    if missing:
        raise ValueError(f'Missing completed-game columns: {sorted(missing)}')
    frame = history.copy()
    frame['GAME_DATE'] = pd.to_datetime(frame.GAME_DATE, errors='raise')
    for date in frame.GAME_DATE:
        game_date(date)
    for column in ('SEASON', 'GAME_ID', 'TEAM_ID', 'TEAM_NAME'):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq('').any():
            raise ValueError(f'Missing {column}')
    if frame.duplicated(['SEASON', 'GAME_ID', 'TEAM_ID']).any():
        raise ValueError('Duplicate team/game identity')
    for _, team in frame.groupby(['SEASON', 'TEAM_ID'], sort=False):
        if not team.GAME_DATE.is_monotonic_increasing:
            raise ValueError('Out-of-order team history')
    for _, pair in frame.groupby(['SEASON', 'GAME_ID'], sort=False):
        if len(pair) != 2 or pair.TEAM_ID.nunique() != 2 or pair.GAME_DATE.nunique() != 1:
            raise ValueError('Every game needs exactly two distinct opponents on one date')
        if 'OPPONENT_TEAM_ID' in pair:
            if list(pair.OPPONENT_TEAM_ID) != list(reversed(pair.TEAM_ID.tolist())):
                raise ValueError('Opponent identity mismatch')
    values = frame[['WIN', *STATS]].apply(pd.to_numeric, errors='raise')
    if np.isinf(values.to_numpy(dtype=float)).any() or not values.WIN.isin([0, 1]).all():
        raise ValueError('Completed games reject infinite statistics and require binary wins')
    frame[values.columns] = values
    return frame


def team_state(history, team, date, season):
    """History must be validated; all same-date games are excluded as a batch."""
    date = game_date(date)
    prior = history[(history.TEAM_NAME == team) & (history.SEASON == season)
                    & (history.GAME_DATE < date)]
    count = len(prior)
    state = {'TEAM_NAME': team, 'TEAM_GAME_NUMBER': count + 1,
             'PREV_GAMES': count, 'PREV_WINS': float(prior.WIN.sum()),
             'SEASON_WIN_PCT': float(prior.WIN.mean()) if count else np.nan,
             'GAME_DATE': prior.GAME_DATE.max() if count else pd.NaT,
             'REST_DAYS': (date - prior.GAME_DATE.max()).days if count else np.nan}
    for feature, source in ROLLING.items():
        state[feature] = float(prior[source].iloc[-5:].mean()) if count else np.nan
    return state


def matchup_features(home, away):
    row = {**home, 'HOME_GAME': 1}
    row.update({f'OPP_{column}': away[column] for column in (*ROLLING, 'REST_DAYS')})
    row.update({f'{column}_DIFF': home[column] - away[column] for column in DIFFERENCES})
    return row


def build_pregame_features(history):
    """Return one-to-one paired features; first-season history is explicitly NaN."""
    history = validate_history(history)
    output = []
    for _, pair in history.groupby(['SEASON', 'GAME_ID'], sort=False):
        records = pair.to_dict('records')
        states = [team_state(history, r['TEAM_NAME'], r['GAME_DATE'], r['SEASON']) for r in records]
        for index, record in enumerate(records):
            opponent = records[1 - index]
            output.append({**matchup_features(states[index], states[1 - index]),
                           **{key: record[key] for key in ('SEASON', 'GAME_ID', 'TEAM_ID', 'TEAM_NAME', 'GAME_DATE')},
                           'OPPONENT_TEAM_ID': opponent['TEAM_ID']})
    return pd.DataFrame(output)
