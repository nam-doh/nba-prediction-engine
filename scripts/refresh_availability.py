"""Collect one timestamped official report; missing reports never imply health."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_collection.player_data.availability import AvailabilityAdapter
from src.data_collection.player_data.snapshots import SnapshotStore


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Exact official timestamped injury PDF URL')
    parser.add_argument('--snapshot-dir', type=Path, default=ROOT / 'data/snapshots/player_data')
    parser.add_argument('--roster-snapshot', type=Path, action='append', default=[])
    args = parser.parse_args(argv)
    store = SnapshotStore(args.snapshot_dir)
    try:
        from nba_api.stats.static import teams
        team_ids = {team['full_name']: team['id'] for team in teams.get_teams()}
        rosters = []
        for path in args.roster_snapshot:
            document = store.read(path)
            if document['dataset'] != 'team_rosters':
                raise ValueError('Expected a verified roster snapshot')
            rosters.extend(document['records'])
        path, cached = AvailabilityAdapter(store).refresh(args.url, rosters=rosters, team_ids=team_ids)
        document = store.read(path)
        print(json.dumps({'snapshot_path': str(path), 'from_cache': cached,
                          'records': document['record_count'], 'source_as_of': document['source_as_of']}))
        return 0
    except Exception as exc:
        print(json.dumps({'error': str(exc), 'availability': 'unknown'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
