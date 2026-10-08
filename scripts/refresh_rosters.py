"""Refresh current NBA team roster snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_collection.player_data.rosters import NbaRosterAdapter
from src.data_collection.player_data.snapshots import SnapshotStore


def _current_team_ids() -> list[int]:
    from nba_api.stats.static.teams import get_teams

    teams = get_teams()
    return sorted(int(team["id"]) for team in teams if team.get("id"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--season", required=True, help="NBA season, for example 2026-27")
    result.add_argument("--team-id", type=int, action="append", dest="team_ids")
    result.add_argument(
        "--snapshot-dir", default="data/snapshots/player_data", type=Path
    )
    result.add_argument("--delay-seconds", type=float, default=3.0)
    result.add_argument("--max-cache-age-minutes", type=float, default=60.0)
    result.add_argument("--force", action="store_true", help="ignore cached snapshots")
    return result


def main(argv: list[str] | None = None, *, adapter: NbaRosterAdapter | None = None) -> int:
    args = parser().parse_args(argv)
    if args.delay_seconds < 0 or args.max_cache_age_minutes < 0:
        parser().error("delay and cache age must be non-negative")
    team_ids = args.team_ids or _current_team_ids()
    adapter = adapter or NbaRosterAdapter(SnapshotStore(args.snapshot_dir))
    max_age = None if args.force else timedelta(minutes=args.max_cache_age_minutes)
    result = adapter.refresh_teams(
        team_ids,
        args.season,
        delay_seconds=args.delay_seconds,
        max_cache_age=max_age,
    )
    summary = {
        "season": args.season,
        "requested_team_count": len(team_ids),
        "successful_team_count": len(result.teams),
        "record_count": result.record_count,
        "cache_hits": sum(team.from_cache for team in result.teams),
        "snapshots": [str(team.snapshot_path) for team in result.teams],
        "failures": {str(key): value for key, value in result.failures.items()},
    }
    print(json.dumps(summary, sort_keys=True))
    return 1 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
