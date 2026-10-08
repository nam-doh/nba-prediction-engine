"""Frozen T003 baseline: read CSV, fit in memory, report JSON to stdout only."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, log_loss, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
TRAIN_START = '2021-07-01'
VALIDATION_START = '2024-07-01'
EXCLUDED_START = '2025-07-01'
FUTURE_HOLDOUT = ['2026-07-01', '2027-07-01']
SEED = 42
FEATURES = ('HOME_GAME', 'SEASON_WIN_PCT', 'WIN_STREAK', 'PTS_ROLL5',
            'FG_PCT_ROLL5', 'FG3_PCT_ROLL5', 'REB_ROLL5', 'AST_ROLL5',
            'TOV_ROLL5', 'PLUS_MINUS_ROLL5', 'WIN_PCT_ROLL5', 'REST_DAYS',
            'OPP_PTS_ROLL5', 'OPP_WIN_PCT_ROLL5', 'OPP_REST_DAYS',
            'PTS_ROLL5_DIFF', 'PLUS_MINUS_ROLL5_DIFF', 'WIN_PCT_ROLL5_DIFF')
GATES = {'log_loss': 'candidate < baseline', 'brier': 'candidate <= baseline',
         'roc_auc': 'candidate >= baseline - 0.005'}


def candidate_passes(baseline, candidate):
    """All frozen probability/out-of-time gates must pass; never promotes."""
    if not all(np.isfinite(m[k]) for m in (baseline, candidate) for k in GATES):
        return False
    return (candidate['log_loss'] < baseline['log_loss'] and
            candidate['brier'] <= baseline['brier'] and
            candidate['roc_auc'] >= baseline['roc_auc'] - 0.005)


def prepare(frame):
    """Partition before filtering; remove incomplete games as pairs."""
    dates = pd.to_datetime(frame['GAME_DATE'], errors='raise')
    if dates.isna().any() or not dates.eq(dates.dt.normalize()).all():
        raise ValueError('Valid calendar dates required')
    selected = frame.loc[(dates >= TRAIN_START) & (dates < EXCLUDED_START)].copy()
    selected['GAME_DATE'] = dates.loc[selected.index]
    if selected.empty:
        raise ValueError('No eligible historical rows')
    for col in ('GAME_ID', 'TEAM_ID'):
        if selected[col].isna().any() or selected[col].astype(str).str.strip().eq('').any():
            raise ValueError('Missing identifier')
    games = selected.groupby('GAME_ID')
    if (games.size().ne(2).any() or games['TEAM_ID'].nunique().ne(2).any()
            or games['GAME_DATE'].nunique().ne(1).any()):
        raise ValueError('Each game requires two distinct teams and one date')
    if not selected['WIN'].isin([0, 1]).all() or games['WIN'].sum().ne(1).any():
        raise ValueError('Each game requires one binary winner')
    values = selected.loc[:, FEATURES].astype(float)
    if np.isinf(values.to_numpy()).any():
        raise ValueError('Infinite features')
    incomplete = selected.loc[values.isna().any(axis=1), 'GAME_ID']
    retained = selected.loc[~selected['GAME_ID'].isin(incomplete)].copy()
    for feature in FEATURES:
        retained[feature] = values.loc[retained.index, feature]
    retained = retained.sort_values(['GAME_DATE', 'GAME_ID', 'TEAM_ID'])
    parts = (retained.loc[retained['GAME_DATE'] < VALIDATION_START].copy(),
             retained.loc[retained['GAME_DATE'] >= VALIDATION_START].copy())
    if any(p.empty or p['WIN'].nunique() != 2 for p in parts):
        raise ValueError('Both partitions need games and both classes')
    return parts, {'excluded_rows': len(frame) - len(selected),
                   'incomplete_rows_removed': len(selected) - len(retained)}


def evaluate(frame):
    (train, validation), counts = prepare(frame)
    model = Pipeline([('scaler', StandardScaler()), ('classifier',
        LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, random_state=SEED,
                           tol=1e-4))])
    model.fit(train.loc[:, FEATURES], train['WIN'])
    probabilities = model.predict_proba(validation.loc[:, FEATURES])[:, 1]
    target = validation['WIN']
    report = {
        'protocol': 'T003-v1', 'seed': SEED, 'features': list(FEATURES),
        'feature_sha256': hashlib.sha256(json.dumps(list(FEATURES), separators=(',', ':')).encode()).hexdigest(),
        'cutoffs': {'train_start': TRAIN_START, 'validation_start': VALIDATION_START,
                    'excluded_start': EXCLUDED_START, 'future_holdout': FUTURE_HOLDOUT},
        'candidate_gates': GATES, 'counts': counts,
        'metrics': {'accuracy': accuracy_score(target, probabilities >= 0.5),
                    'roc_auc': roc_auc_score(target, probabilities),
                    'log_loss': log_loss(target, probabilities, labels=[0, 1]),
                    'brier': brier_score_loss(target, probabilities)},
        'versions': {'python': platform.python_version(), 'pandas': pd.__version__,
                     'numpy': np.__version__, 'sklearn': sklearn.__version__},
        'model': model.named_steps['classifier'].get_params(),
    }
    for name, part in zip(('train', 'validation'), (train, validation)):
        report[name] = {'rows': len(part), 'games': part['GAME_ID'].nunique(),
                        'first_date': str(part['GAME_DATE'].min().date()),
                        'last_date': str(part['GAME_DATE'].max().date())}
    return report, model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data/processed/team_game_modeling.csv')
    args = parser.parse_args()
    # Hash and parse the same snapshot, without writing data or model artifacts.
    import io
    payload = args.data.read_bytes()
    report, _ = evaluate(pd.read_csv(io.BytesIO(payload), dtype={'GAME_ID': str, 'TEAM_ID': str}))
    report['data_sha256'] = hashlib.sha256(payload).hexdigest()
    report['data_path'] = str(args.data)
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
