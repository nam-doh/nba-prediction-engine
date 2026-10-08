"""Look up unconfirmed player news; never modify official availability."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_collection.player_data.news import PlayerNewsAdapter
from src.data_collection.player_data.snapshots import SnapshotStore


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument('--player-id', type=int)
    identity.add_argument('--name')
    parser.add_argument('--snapshot-dir', type=Path, default=ROOT / 'data/snapshots/player_data')
    parser.add_argument('--roster-snapshot', type=Path, action='append', default=[])
    args = parser.parse_args(argv)
    store = SnapshotStore(args.snapshot_dir)
    try:
        rosters = []
        for path in args.roster_snapshot:
            document = store.read(path)
            if document['dataset'] != 'team_rosters':
                raise ValueError('Expected a verified roster snapshot')
            rosters.extend(document['records'])
        records, path, cached = PlayerNewsAdapter(store).lookup(player_id=args.player_id, name=args.name, rosters=rosters)
        print(json.dumps({'records': records, 'snapshot_path': str(path), 'from_cache': cached}, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'error': str(exc), 'availability': 'unknown'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
