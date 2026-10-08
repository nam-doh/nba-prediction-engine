"""Refresh an NBA season's player game-log snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_collection.player_data.snapshots import SnapshotStore
from src.data_collection.player_data.statistics import NbaPlayerStatsAdapter


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--season", required=True, help="NBA season, for example 2025-26")
    result.add_argument("--season-type", default="Regular Season")
    result.add_argument(
        "--snapshot-dir", default="data/snapshots/player_data", type=Path
    )
    result.add_argument("--max-cache-age-minutes", type=float, default=360.0)
    result.add_argument("--force", action="store_true", help="ignore cached snapshots")
    return result


def main(
    argv: list[str] | None = None,
    *,
    adapter: NbaPlayerStatsAdapter | None = None,
) -> int:
    args = parser().parse_args(argv)
    if args.max_cache_age_minutes < 0:
        parser().error("cache age must be non-negative")
    adapter = adapter or NbaPlayerStatsAdapter(SnapshotStore(args.snapshot_dir))
    max_age = None if args.force else timedelta(minutes=args.max_cache_age_minutes)
    result = adapter.refresh(
        args.season, args.season_type, max_cache_age=max_age
    )
    summary = {
        "season": args.season,
        "season_type": args.season_type,
        "record_count": len(result.records),
        "cache_hit": result.from_cache,
        "snapshot": str(result.snapshot_path),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
