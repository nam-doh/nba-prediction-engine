import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from scripts.refresh_player_stats import main as stats_main
from src.data_collection.player_data.contracts import ProviderError, ValidationError
from src.data_collection.player_data.snapshots import SnapshotStore
from src.data_collection.player_data.statistics import (
    NbaPlayerStatsAdapter,
    PlayerStatsResult,
)


HEADERS = [
    "SEASON_YEAR",
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ID",
    "TEAM_ABBREVIATION",
    "TEAM_NAME",
    "GAME_ID",
    "GAME_DATE",
    "MATCHUP",
    "WL",
    "MIN",
    "PTS",
    "REB",
    "AST",
    "PLUS_MINUS",
]


def row(
    *,
    player_id=101,
    team_id=1610612738,
    game_id="0022600001",
    game_date="2026-10-01",
    minutes=31.5,
    points=22,
):
    return [
        "2026-27",
        player_id,
        "Example Player",
        team_id,
        "BOS",
        "Boston Celtics",
        game_id,
        game_date,
        "BOS vs. NYK",
        "W",
        minutes,
        points,
        8,
        6,
        4,
    ]


def payload(*rows):
    return {
        "resource": "playergamelogs",
        "resultSets": [
            {"name": "PlayerGameLogs", "headers": HEADERS, "rowSet": list(rows)}
        ],
    }


class PlayerStatsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = SnapshotStore(self.temporary.name)
        self.now = datetime(2026, 10, 8, 18, 0, tzinfo=timezone.utc)

    def adapter(self, fetcher):
        return NbaPlayerStatsAdapter(
            self.store, fetcher=fetcher, clock=lambda: self.now
        )

    def test_normalizes_temporal_ids_stats_and_snapshot_provenance(self):
        fixture = payload(row())
        result = self.adapter(lambda *_: fixture).refresh(
            "2026-27", max_cache_age=None
        )
        record = result.records[0]
        self.assertEqual(record["game_id"], "0022600001")
        self.assertEqual(record["game_date"], "2026-10-01")
        self.assertEqual(record["player_id"], 101)
        self.assertEqual(record["team_id"], 1610612738)
        self.assertEqual(record["minutes"], 31.5)
        self.assertEqual(record["points"], 22.0)
        self.assertIsNone(record["steals"])
        self.assertEqual(record["retrieved_at"], "2026-10-08T18:00:00.000000Z")
        snapshot = self.store.read(result.snapshot_path)
        self.assertEqual(snapshot["request"]["season_type"], "Regular Season")
        self.assertEqual(snapshot["records"], list(result.records))
        self.assertEqual(snapshot["raw_payload"], fixture)

    def test_cache_avoids_repeated_provider_request(self):
        calls = []

        def fetcher(*args):
            calls.append(args)
            return payload(row())

        adapter = self.adapter(fetcher)
        first = adapter.refresh("2026-27")
        second = adapter.refresh("2026-27")
        self.assertFalse(first.from_cache)
        self.assertTrue(second.from_cache)
        self.assertEqual(len(calls), 1)
        self.assertEqual(first.snapshot_path, second.snapshot_path)

    def test_rejects_duplicates_bad_dates_minutes_and_season_mismatch(self):
        duplicate = payload(row(), row(points=30))
        with self.assertRaisesRegex(ValidationError, "duplicate player-game"):
            self.adapter(lambda *_: duplicate).refresh(
                "2026-27", max_cache_age=None
            )

        with self.assertRaisesRegex(ValidationError, "recognized date"):
            self.adapter(lambda *_: payload(row(game_date="not-a-date"))).refresh(
                "2026-27", max_cache_age=None
            )

        with self.assertRaisesRegex(ValidationError, "non-negative"):
            self.adapter(lambda *_: payload(row(minutes=-1))).refresh(
                "2026-27", max_cache_age=None
            )

        mismatched = row()
        mismatched[0] = "2025-26"
        with self.assertRaisesRegex(ValidationError, "does not match requested"):
            self.adapter(lambda *_: payload(mismatched)).refresh(
                "2026-27", max_cache_age=None
            )

    def test_provider_failure_creates_no_snapshot_or_fallback(self):
        def fail(*_args):
            raise TimeoutError("upstream timed out")

        with self.assertRaisesRegex(ProviderError, "upstream timed out"):
            self.adapter(fail).refresh("2026-27", max_cache_age=None)
        self.assertIsNone(
            self.store.latest(
                provider="nba_stats", dataset="player_game_logs"
            )
        )

    def test_cli_prints_machine_readable_snapshot_summary(self):
        fixture_result = PlayerStatsResult(
            records=({"player_id": 1}, {"player_id": 2}),
            snapshot_path=Path("/tmp/player-stats.json"),
            from_cache=True,
        )

        class FixtureAdapter:
            def refresh(self, *_args, **_kwargs):
                return fixture_result

        output = io.StringIO()
        with redirect_stdout(output):
            code = stats_main(
                ["--season", "2026-27", "--season-type", "Playoffs"],
                adapter=FixtureAdapter(),
            )
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "cache_hit": True,
                "record_count": 2,
                "season": "2026-27",
                "season_type": "Playoffs",
                "snapshot": "/tmp/player-stats.json",
            },
        )


if __name__ == "__main__":
    unittest.main()
