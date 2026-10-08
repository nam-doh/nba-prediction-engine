import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.data_collection.player_data.contracts import ValidationError
from src.data_collection.player_data.snapshots import SnapshotError, SnapshotStore


class SnapshotStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = SnapshotStore(self.temporary.name)
        self.retrieved_at = datetime(2026, 10, 8, 15, 30, tzinfo=timezone.utc)

    def write(self, **overrides):
        values = {
            "provider": "nba_stats",
            "dataset": "rosters",
            "request": {"season": "2026-27", "team_id": 1610612738},
            "source_url": "https://example.test/stats?team=bos&api_key=secret#fragment",
            "retrieved_at": self.retrieved_at,
            "records": [{"player_id": 1, "team_id": 1610612738}],
            "raw_payload": {"resultSets": []},
        }
        values.update(overrides)
        return self.store.write(**values)

    def test_round_trip_is_immutable_deterministic_and_redacted(self):
        path = self.write()
        first_bytes = path.read_bytes()
        self.assertEqual(path, self.write())
        self.assertEqual(first_bytes, path.read_bytes())

        document = self.store.read(path)
        self.assertEqual(document["record_count"], 1)
        self.assertEqual(document["retrieved_at"], "2026-10-08T15:30:00.000000Z")
        self.assertEqual(
            document["source_url"],
            "https://example.test/stats?team=bos&api_key=REDACTED",
        )
        self.assertEqual(len(document["content_sha256"]), 64)

        path.write_text("different", encoding="utf-8")
        with self.assertRaisesRegex(SnapshotError, "refusing to overwrite"):
            self.write()

    def test_latest_filters_exact_request_and_verifies_hash(self):
        first = self.write()
        second_request = {"season": "2026-27", "team_id": 1610612744}
        second = self.write(
            request=second_request,
            retrieved_at=self.retrieved_at + timedelta(minutes=1),
            records=[{"player_id": 2, "team_id": 1610612744}],
        )
        latest_path, latest = self.store.latest(
            provider="nba_stats", dataset="rosters"
        )
        self.assertEqual(latest_path, second)
        self.assertEqual(latest["request"], second_request)
        filtered_path, _ = self.store.latest(
            provider="nba_stats",
            dataset="rosters",
            request={"season": "2026-27", "team_id": 1610612738},
        )
        self.assertEqual(filtered_path, first)

        document = json.loads(second.read_text(encoding="utf-8"))
        document["records"][0]["player_id"] = 99
        second.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(SnapshotError, "hash does not match"):
            self.store.read(second)

    def test_rejects_naive_time_unsafe_paths_bad_urls_and_nonfinite_json(self):
        with self.assertRaisesRegex(ValidationError, "timezone-aware"):
            self.write(retrieved_at=datetime(2026, 10, 8))
        with self.assertRaisesRegex(SnapshotError, "safe path"):
            self.write(provider="../escape")
        with self.assertRaisesRegex(ValidationError, "absolute HTTP"):
            self.write(source_url="/relative")
        with self.assertRaisesRegex(SnapshotError, "finite JSON"):
            self.write(records=[{"minutes": float("nan")}])

    def test_read_rejects_paths_outside_store_and_corrupt_json(self):
        outside = Path(self.temporary.name).parent / "outside-player-snapshot.json"
        outside.write_text("{}", encoding="utf-8")
        self.addCleanup(outside.unlink, missing_ok=True)
        with self.assertRaisesRegex(SnapshotError, "outside the store"):
            self.store.read(outside)

        path = self.write()
        path.write_text("not json", encoding="utf-8")
        with self.assertRaisesRegex(SnapshotError, "cannot read"):
            self.store.read(path)


if __name__ == "__main__":
    unittest.main()
