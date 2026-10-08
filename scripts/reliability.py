"""Measure frozen T003 validation probability reliability without writes."""
import argparse
import hashlib
import io
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

try:
    from scripts.baseline import (
        EXCLUDED_START,
        FEATURES,
        FUTURE_HOLDOUT,
        ROOT,
        SEED,
        TRAIN_START,
        VALIDATION_START,
        evaluate,
        prepare,
    )
except ModuleNotFoundError:
    from baseline import (
        EXCLUDED_START,
        FEATURES,
        FUTURE_HOLDOUT,
        ROOT,
        SEED,
        TRAIN_START,
        VALIDATION_START,
        evaluate,
        prepare,
    )

PROTOCOL_ID = 'T003-v1'
CALIBRATION_BIN_EDGES = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5,
                         0.6, 0.7, 0.8, 0.9, 1.0)


def _validated_arrays(target, probabilities):
    """Return finite binary targets and probabilities in the unit interval."""
    target = np.asarray(target)
    probabilities = np.asarray(probabilities, dtype=float)
    if target.ndim != 1 or probabilities.ndim != 1 or len(target) != len(probabilities):
        raise ValueError('Target and probability vectors must have equal one-dimensional shape')
    if len(target) == 0:
        raise ValueError('At least one probability is required')
    if pd.isna(target).any() or not np.isin(target, [0, 1]).all():
        raise ValueError('Targets must be non-missing binary values')
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError('Probabilities must be finite values in [0, 1]')
    return target.astype(int), probabilities


def calibration_bins(target, probabilities):
    """Summarize fixed [0.0, 0.1), ..., [0.9, 1.0] probability bins."""
    target, probabilities = _validated_arrays(target, probabilities)
    indices = np.digitize(probabilities, CALIBRATION_BIN_EDGES[1:-1], right=False)
    bins = []
    for index, (lower, upper) in enumerate(
            zip(CALIBRATION_BIN_EDGES[:-1], CALIBRATION_BIN_EDGES[1:])):
        selected = indices == index
        count = int(selected.sum())
        bins.append({
            'index': index,
            'lower': lower,
            'upper': upper,
            'count': count,
            'positive_count': int(target[selected].sum()),
            'mean_predicted_probability': (
                None if count == 0 else float(probabilities[selected].mean())
            ),
            'observed_prevalence': (
                None if count == 0 else float(target[selected].mean())
            ),
        })
    return bins


def probability_summary(target, probabilities):
    """Return validation metrics and calibration data for supplied probabilities."""
    target, probabilities = _validated_arrays(target, probabilities)
    if np.unique(target).size != 2:
        raise ValueError('Both target classes are required for validation metrics')
    return {
        'metrics': {
            'accuracy': float(accuracy_score(target, probabilities >= 0.5)),
            'roc_auc': float(roc_auc_score(target, probabilities)),
            'log_loss': float(log_loss(target, probabilities, labels=[0, 1])),
            'brier': float(brier_score_loss(target, probabilities)),
        },
        'sample_count': int(len(target)),
        'class_counts': {
            '0': int((target == 0).sum()),
            '1': int((target == 1).sum()),
        },
        'class_prevalence': float(target.mean()),
        'calibration': {
            'bin_edges': list(CALIBRATION_BIN_EDGES),
            'bins': calibration_bins(target, probabilities),
        },
    }


def reliability_from_frame(frame):
    """Evaluate only the frozen T003 validation partition in memory."""
    baseline, model = evaluate(frame)
    (train, validation), _ = prepare(frame)
    probabilities = model.predict_proba(validation.loc[:, FEATURES])[:, 1]
    summary = probability_summary(validation['WIN'].to_numpy(), probabilities)
    return {
        'protocol_id': PROTOCOL_ID,
        'features': list(FEATURES),
        'seed': SEED,
        'feature_sha256': baseline['feature_sha256'],
        'cutoffs': {
            'train_start': TRAIN_START,
            'validation_start': VALIDATION_START,
            'excluded_start': EXCLUDED_START,
            'future_holdout': list(FUTURE_HOLDOUT),
        },
        'counts': baseline['counts'],
        'partitions': {
            'train': baseline['train'],
            'validation': {
                **baseline['validation'],
                'sample_count': summary['sample_count'],
                'class_counts': summary['class_counts'],
                'class_prevalence': summary['class_prevalence'],
            },
        },
        'metrics': summary['metrics'],
        'calibration': summary['calibration'],
        'preprocessing': {
            'fit_partition': 'train',
            'scored_partition': 'validation',
            'train_rows_used': int(len(train)),
        },
        'versions': {
            'python': platform.python_version(),
            'pandas': pd.__version__,
            'numpy': np.__version__,
            'sklearn': sklearn.__version__,
        },
    }


def report_from_bytes(payload):
    """Parse one CSV snapshot and return a deterministic reliability report."""
    frame = pd.read_csv(
        io.BytesIO(payload), dtype={'GAME_ID': str, 'TEAM_ID': str}
    )
    report = reliability_from_frame(frame)
    report['data_sha256'] = hashlib.sha256(payload).hexdigest()
    return report


def report_from_path(path):
    """Read one input snapshot without changing it or writing an output file."""
    return report_from_bytes(path.read_bytes())


def render(report):
    """Serialize a report with stable key ordering and no non-finite JSON."""
    return json.dumps(report, indent=2, sort_keys=True, allow_nan=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--data', type=Path, default=ROOT / 'data/processed/team_game_modeling.csv'
    )
    args = parser.parse_args(argv)
    print(render(report_from_path(args.data)))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError) as error:
        raise SystemExit(f'error: {error}')
