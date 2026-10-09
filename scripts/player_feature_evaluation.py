"""Read-only chronological player-feature comparison; never promotes artifacts."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.base import clone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.baseline import FEATURES as BASE_FEATURES, candidate_passes, evaluate, prepare
from scripts.reliability import probability_summary
from src.data_collection.player_data.contracts import PlayerDataError
from src.data_collection.player_data.snapshots import SnapshotStore
from src.modeling.player_contributions import FEATURES as PLAYER_FEATURES, estimate_contributions


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def evaluate_players(payload, manifest, store):
    frame = pd.read_csv(io.BytesIO(payload), dtype={'GAME_ID': str, 'TEAM_ID': str})
    (train, validation), _ = prepare(frame)
    # Reproduce the chronological baseline before any candidate fit.
    baseline, baseline_model = evaluate(frame)
    baseline_summary = probability_summary(validation.WIN, baseline_model.predict_proba(validation.loc[:, BASE_FEATURES])[:,1])
    report = {'protocol': 'T018-v1', 'baseline': {**baseline, **baseline_summary},
              'data_sha256': hashlib.sha256(payload).hexdigest(), 'manifest_sha256': digest(manifest),
              'production_promoted': False, 'accepted_features': [], 'candidates': {}, 'blockers': []}
    keys = {(str(r.GAME_ID), str(r.TEAM_ID)) for r in pd.concat([train,validation]).itertuples()}
    entries = {}
    for entry in manifest:
        key = (str(entry['game_id']), str(entry['team_id']))
        if key not in keys:
            # Exposed/future entries are not opened or inspected.
            continue
        if key in entries:
            raise ValueError('Duplicate team/game manifest identity')
        entries[key] = entry
    missing = keys - entries.keys()
    if missing:
        report['blockers'].append(f'Missing pregame roster/statistics snapshot coverage for {len(missing)} retained team/game rows')
        report['status'] = 'blocked'
        return report
    inputs, source_hashes = {}, set()
    for key, entry in entries.items():
        documents = {}
        for kind in ('roster','statistics','availability'):
            documents[kind] = store.read(store.root / entry[kind]) if entry.get(kind) else None
            if documents[kind]:
                source_hashes.add(documents[kind]['content_sha256'])
        inputs[key] = documents
    report['snapshot_hashes'] = sorted(source_hashes)
    all_rows = pd.concat([train, validation])
    outputs = {'player_statistics': [], 'availability_scenarios': []}
    availability_missing = 0
    for row in all_rows.itertuples():
        documents = inputs[(str(row.GAME_ID), str(row.TEAM_ID))]
        when = pd.Timestamp(row.GAME_DATE).tz_localize('UTC').isoformat()
        args = dict(roster=documents['roster'], statistics=documents['statistics'], team_id=int(row.TEAM_ID), game_time=when)
        statistical = estimate_contributions(**args)
        outputs['player_statistics'].append(statistical['features'])
        available = documents['availability']
        if not available or not any(r.get('team_id') == int(row.TEAM_ID) and r.get('game_date') == str(row.GAME_DATE.date()) for r in available['records']):
            availability_missing += 1
        else:
            scenario = estimate_contributions(**args, availability=available)
            outputs['availability_scenarios'].append(scenario['features'])
    if availability_missing:
        report['blockers'].append(f'Missing game-specific official pregame reports for {availability_missing} retained team/game rows')
    for name, extra in (('player_statistics', ('rotation_strength_spread',)), ('availability_scenarios', PLAYER_FEATURES)):
        if name == 'availability_scenarios' and availability_missing:
            continue
        additions = pd.DataFrame(outputs[name], index=all_rows.index)
        features = [*BASE_FEATURES, *extra]
        combined = pd.concat([all_rows.loc[:, BASE_FEATURES], additions.loc[:,extra]], axis=1)
        if not np.isfinite(combined.to_numpy(dtype=float)).all():
            raise ValueError('Nonfinite player features')
        candidate = clone(baseline_model)
        candidate.fit(combined.iloc[:len(train)], train.WIN)
        probabilities = candidate.predict_proba(combined.iloc[len(train):])[:,1]
        summary = probability_summary(validation.WIN, probabilities)
        report['candidates'][name] = {**summary, 'features': features, 'feature_sha256': digest(features),
                                      'train_rows': len(train), 'validation_rows': len(validation),
                                      'gate_passed': candidate_passes(baseline_summary['metrics'], summary['metrics']),
                                      'preprocessing_fit_partition': 'train'}
    report['status'] = 'blocked' if report['blockers'] else 'evaluated_not_promoted'
    # A gate pass never authorizes integration or promotion by itself.
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data/processed/team_game_modeling.csv')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--snapshot-dir', type=Path, default=ROOT / 'data/snapshots/player_data')
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text()) if args.manifest else []
        if not isinstance(manifest, list):
            raise ValueError('Manifest must be a JSON list')
        report = evaluate_players(args.data.read_bytes(), manifest, SnapshotStore(args.snapshot_dir))
    except (OSError, ValueError, KeyError, TypeError, PlayerDataError) as exc:
        print(json.dumps({'status':'blocked', 'production_promoted':False, 'error':str(exc)}))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
    return 2 if report['status'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
