"""Strict date-as-of features from completed games, never exported pregame values."""
from __future__ import annotations

import numpy as np
import pandas as pd

STATS = ('PTS', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PLUS_MINUS')
ROLLING = {f'{s}_ROLL5': s for s in STATS} | {'WIN_PCT_ROLL5': 'WIN'}
DIFFERENCES = ('PTS_ROLL5', 'FG_PCT_ROLL5', 'FG3_PCT_ROLL5', 'REB_ROLL5',
               'AST_ROLL5', 'TOV_ROLL5', 'PLUS_MINUS_ROLL5', 'WIN_PCT_ROLL5', 'REST_DAYS')
REQUIRED = ('SEASON', 'GAME_ID', 'TEAM_ID', 'TEAM_ABBREVIATION', 'TEAM_NAME',
            'GAME_DATE', 'MATCHUP', 'WIN', *STATS)


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
        orientations = []
        for row in pair.to_dict('records'):
            matchup = str(row['MATCHUP']).split()
            if len(matchup) != 3 or matchup[0] != str(row['TEAM_ABBREVIATION']) or matchup[1] not in {'vs.', '@'}:
                raise ValueError('Matchup must identify team and home/away orientation')
            opponent = next(other for other in pair.to_dict('records') if other['TEAM_ID'] != row['TEAM_ID'])
            expected_opponent = (opponent.get('TEAM_ABBREVIATION') or
                                 str(row.get('OPPONENT_ABBREVIATION', '')))
            if matchup[2] != expected_opponent:
                raise ValueError('Matchup opponent abbreviation mismatch')
            orientations.append(matchup[1] == 'vs.')
        if orientations.count(True) not in {0, 1}:
            raise ValueError('A game cannot have multiple home teams')
    values = frame[['WIN', *STATS]].apply(pd.to_numeric, errors='raise')
    if np.isinf(values.to_numpy(dtype=float)).any() or not values.WIN.isin([0, 1]).all():
        raise ValueError('Completed games reject infinite statistics and require binary wins')
    frame[values.columns] = values
    return frame


def _state_from_prior(records, team, date):
    date = game_date(date)
    count = len(records)
    wins = sum(row['WIN'] for row in records)
    streak = 0
    for row in reversed(records):
        if not row['WIN']:
            break
        streak += 1
    state = {'TEAM_NAME': team, 'TEAM_GAME_NUMBER': count + 1,
             'PREV_GAMES': count, 'PREV_WINS': float(wins),
             'PREV_WIN': float(records[-1]['WIN']) if count else np.nan,
             'PREV_PTS': float(records[-1]['PTS']) if count else np.nan,
             'WIN_STREAK': streak,
             'SEASON_WIN_PCT': wins / count if count else np.nan,
             'GAME_DATE': pd.Timestamp(records[-1]['GAME_DATE']) if count else pd.NaT,
             'REST_DAYS': (date - pd.Timestamp(records[-1]['GAME_DATE'])).days if count else np.nan}
    for feature, source in ROLLING.items():
        values = [row[source] for row in records[-5:] if not pd.isna(row[source])]
        state[feature] = float(np.mean(values)) if values else np.nan
    return state


def team_state(history, team, date, season):
    """History must be validated; all same-date games are excluded as a batch."""
    date = game_date(date)
    prior = history[(history.TEAM_NAME == team) & (history.SEASON == season)
                    & (history.GAME_DATE < date)]
    return _state_from_prior(prior.to_dict('records'), team, date)


def matchup_features(home, away, *, home_game=1):
    row = {**home, 'HOME_GAME': home_game}
    row.update({f'OPP_{column}': away[column] for column in (*ROLLING, 'REST_DAYS')})
    row.update({f'{column}_DIFF': home[column] - away[column] for column in DIFFERENCES})
    return row


def build_pregame_features(history):
    """Return one-to-one paired features; same-date team games share prior state."""
    history = validate_history(history)
    states = {}
    for (season, team_id), rows in history.groupby(['SEASON', 'TEAM_ID'], sort=False):
        prior = []
        for date, batch in rows.groupby('GAME_DATE', sort=False):
            state = _state_from_prior(prior, batch.iloc[0]['TEAM_NAME'], date)
            for record in batch.to_dict('records'):
                states[(season, record['GAME_ID'], team_id)] = state
            prior.extend(batch.to_dict('records'))
    output = []
    for (season, game_id), pair in history.groupby(['SEASON', 'GAME_ID'], sort=False):
        records = pair.to_dict('records')
        for record in records:
            opponent = next(other for other in records if other['TEAM_ID'] != record['TEAM_ID'])
            output.append({
                **matchup_features(states[(season, game_id, record['TEAM_ID'])],
                                   states[(season, game_id, opponent['TEAM_ID'])],
                                   home_game=int(record['MATCHUP'].split()[1] == 'vs.')),
                **{key: record[key] for key in ('SEASON', 'GAME_ID', 'TEAM_ID', 'TEAM_NAME', 'GAME_DATE')},
                'OPPONENT_TEAM_ID': opponent['TEAM_ID'],
            })
    return pd.DataFrame(output)
