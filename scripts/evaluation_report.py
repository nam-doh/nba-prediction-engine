"""Reproduce the frozen T003 training/validation evaluation without writes."""
import argparse
import hashlib
import io
import json
import platform
from pathlib import Path
import sys

import pandas as pd

try:
    from scripts.baseline import (
        FEATURES,
        FUTURE_HOLDOUT,
        EXCLUDED_START,
        ROOT,
        SEED,
        TRAIN_START,
        VALIDATION_START,
        evaluate,
    )
except ModuleNotFoundError:
    from baseline import (
        FEATURES,
        FUTURE_HOLDOUT,
        EXCLUDED_START,
        ROOT,
        SEED,
        TRAIN_START,
        VALIDATION_START,
        evaluate,
    )

PROTOCOL_ID = 'T003-v1'


def report_from_bytes(payload):
    """Parse one CSV snapshot and return its deterministic evaluation report."""
    frame = pd.read_csv(
        io.BytesIO(payload), dtype={'GAME_ID': str, 'TEAM_ID': str}
    )
    baseline, _ = evaluate(frame)
    partitions = {
        'train': {
            'interval': {'start': TRAIN_START, 'end': VALIDATION_START},
            **baseline['train'],
        },
        'validation': {
            'interval': {'start': VALIDATION_START, 'end': EXCLUDED_START},
            **baseline['validation'],
        },
    }
    return {
        'protocol_id': PROTOCOL_ID,
        'data_sha256': hashlib.sha256(payload).hexdigest(),
        'features': list(FEATURES),
        'feature_sha256': baseline['feature_sha256'],
        'seed': SEED,
        'versions': {
            'python': platform.python_version(),
            'pandas': pd.__version__,
            'numpy': baseline['versions']['numpy'],
            'sklearn': baseline['versions']['sklearn'],
        },
        'cutoffs': {
            'train_start': TRAIN_START,
            'validation_start': VALIDATION_START,
            'excluded_start': EXCLUDED_START,
            'future_holdout': list(FUTURE_HOLDOUT),
        },
        'counts': baseline['counts'],
        'partitions': partitions,
        'metrics': baseline['metrics'],
    }


def report_from_path(path):
    """Read a CSV snapshot once and evaluate it without changing the file."""
    return report_from_bytes(path.read_bytes())


def render(report):
    """Serialize a report with stable key ordering and JSON formatting."""
    return json.dumps(report, indent=2, sort_keys=True, allow_nan=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--data', type=Path, default=ROOT / 'data/processed/team_game_modeling.csv'
    )
    args = parser.parse_args(argv)
    try:
        report = report_from_path(args.data)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(render(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
