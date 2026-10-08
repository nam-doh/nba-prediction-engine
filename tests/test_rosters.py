import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.refresh_rosters import main as roster_main
from src.data_collection.player_data.contracts import ProviderError, ValidationError
from src.data_collection.player_data.rosters import (
    NbaRosterAdapter,
    RosterBatchResult,
    RosterTeamResult,
)
from src.data_collection.player_data.snapshots import SnapshotStore


HEADERS = ["TeamID", "SEASON", "PLAYER", "PLAYER_SLUG", "NUM", "POSITION", "PLAYER_ID"]


def payload(*rows):
    return {
        "resource": "commonteamroster",
        "resultSets": [
            {"name": "CommonTeamRoster", "headers": HEADERS, "rowSet": list(rows)}
        ],
    }


class RosterAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = SnapshotStore(self.temporary.name)
        self.now = datetime(2026, 10, 8, 16, 0, tzinfo=timezone.utc)

    def adapter(self, fetcher):
        return NbaRosterAdapter(self.store, fetcher=fetcher, clock=lambda: self.now)

    def test_normalizes_stable_ids_and_allows_duplicate_names(self):
        team_id = 1610612738
        fixture = payload(
            [team_id, "2026", "Alex Smith", "alex-smith-1", "1", "G", 101],
            [team_id, "2026", "Alex Smith", "alex-smith-2", None, "F", 202],
        )
        result = self.adapter(lambda *_: fixture).refresh_team(
            team_id, "2026-27", max_cache_age=None
        )
        self.assertFalse(result.from_cache)
        self.assertEqual([record["player_id"] for record in result.records], [101, 202])
        self.assertEqual(result.records[0]["team_id"], team_id)
        self.assertEqual(result.records[1]["jersey_number"], None)
        self.assertEqual(
            result.records[0]["retrieved_at"], "2026-10-08T16:00:00.000000Z"
        )
        snapshot = self.store.read(result.snapshot_path)
        self.assertEqual(snapshot["raw_payload"], fixture)
        self.assertEqual(snapshot["records"], list(result.records))

    def test_cache_prevents_second_request_and_preserves_trade_memberships(self):
        calls = []
        player_id = 404

        def fetcher(team_id, _season, _timeout):
            calls.append(team_id)
            return payload([team_id, "2026", "Trade Player", "trade-player", "4", "G", player_id])

        adapter = self.adapter(fetcher)
        boston = adapter.refresh_team(1610612738, "2026-27")
        cached = adapter.refresh_team(1610612738, "2026-27")
        golden_state = adapter.refresh_team(1610612744, "2026-27")
        self.assertFalse(boston.from_cache)
        self.assertTrue(cached.from_cache)
        self.assertEqual(calls, [1610612738, 1610612744])
        self.assertEqual(
            {boston.records[0]["team_id"], golden_state.records[0]["team_id"]},
            {1610612738, 1610612744},
        )

    def test_partial_failure_retains_successful_snapshot_and_skips_fabrication(self):
        first = 1610612738
        second = 1610612744

        def fetcher(team_id, _season, _timeout):
            if team_id == second:
                raise TimeoutError("timed out")
            return payload([team_id, "2026", "Known Player", "known", "7", "F", 707])

        sleeps = []
        result = self.adapter(fetcher).refresh_teams(
            [first, second],
            "2026-27",
            delay_seconds=3,
            max_cache_age=None,
            sleeper=sleeps.append,
        )
        self.assertEqual(len(result.teams), 1)
        self.assertTrue(result.teams[0].snapshot_path.exists())
        self.assertIn(second, result.failures)
        self.assertIn("timed out", result.failures[second])
        self.assertEqual(result.record_count, 1)
        self.assertEqual(sleeps, [3])

    def test_rejects_duplicate_or_malformed_identity_rows(self):
        team_id = 1610612738
        duplicate = payload(
            [team_id, "2026", "One", "one", "1", "G", 101],
            [team_id, "2026", "One Again", "one", "1", "G", 101],
        )
        with self.assertRaisesRegex(ValidationError, "duplicate roster identity"):
            self.adapter(lambda *_: duplicate).refresh_team(
                team_id, "2026-27", max_cache_age=None
            )

        wrong_team = payload([1610612744, "2026", "One", "one", "1", "G", 101])
        with self.assertRaisesRegex(ValidationError, "does not match"):
            self.adapter(lambda *_: wrong_team).refresh_team(
                team_id, "2026-27", max_cache_age=None
            )

        with self.assertRaisesRegex(ProviderError, "contains no players"):
            self.adapter(lambda *_: payload()).refresh_team(
                team_id, "2026-27", max_cache_age=None
            )

    def test_cli_reports_partial_failure_with_nonzero_exit(self):
        team = RosterTeamResult(
            team_id=1,
            records=({"player_id": 2},),
            snapshot_path=Path("/tmp/roster.json"),
            from_cache=False,
        )

        class FixtureAdapter:
            def refresh_teams(self, *_args, **_kwargs):
                return RosterBatchResult((team,), {2: "provider unavailable"})

        output = io.StringIO()
        with redirect_stdout(output):
            code = roster_main(
                ["--season", "2026-27", "--team-id", "1", "--team-id", "2"],
                adapter=FixtureAdapter(),
            )
        self.assertEqual(code, 1)
        summary = json.loads(output.getvalue())
        self.assertEqual(summary["record_count"], 1)
        self.assertEqual(summary["failures"], {"2": "provider unavailable"})


if __name__ == "__main__":
    unittest.main()
