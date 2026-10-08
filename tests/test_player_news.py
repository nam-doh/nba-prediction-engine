from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.data_collection.player_data.contracts import ProviderError, ValidationError
from src.data_collection.player_data.news import PlayerNewsAdapter, reported_status, fetch_news
from src.data_collection.player_data.snapshots import SnapshotStore


class NewsTests(unittest.TestCase):
    def test_explicit_body_assertions_only_and_uncertainty(self):
        self.assertEqual(reported_status('Alex Example', 'Alex Example is listed as out tonight.')[0], None)
        self.assertEqual(reported_status('Alex Example', 'Alex Example is listed as out for tonight.')[0], 'out')
        for text in ('Alex Example may be out.', 'Alex Example is not ruled out.',
                     'Could Alex Example be injured?', 'Someone else is listed as out.',
                     'Alex Example is listed as out. Alex Example is listed as available.'):
            self.assertIsNone(reported_status('Alex Example', text)[0])

    def test_cache_stale_future_irrelevant_and_headline_only(self):
        now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
        def article(title, body, published, url):
            return dict(title=title, description=body, publishedAt=published.isoformat(), url=url)
        payload = {'articles': [
            article('Alex Example out injured', 'Preview only', now-timedelta(hours=23), 'https://example.org/1'),
            article('Alex Example update', 'Alex Example is listed as questionable.', now-timedelta(hours=25), 'https://example.org/2'),
            article('Other news', 'Other player', now, 'https://example.org/3'),
            article('Alex Example update', 'Future', now+timedelta(hours=1), 'https://example.org/4')]}
        with tempfile.TemporaryDirectory() as root:
            clock = Mock(return_value=now)
            fetch = Mock(return_value=payload)
            adapter = PlayerNewsAdapter(SnapshotStore(root), fetcher=fetch, clock=clock)
            rows, path, cached = adapter.lookup(name='Alex Example')
            self.assertEqual([r['source_url'] for r in rows], ['https://example.org/1','https://example.org/2'])
            self.assertIsNone(rows[0]['reported_availability'])
            self.assertFalse(rows[0]['stale'])
            self.assertEqual(rows[1]['reported_availability'], 'questionable')
            self.assertTrue(rows[1]['stale'])
            self.assertFalse(rows[1]['official'])
            self.assertTrue(all(r['current_availability'] is None for r in rows))
            clock.return_value += timedelta(hours=2)
            rows, cached_path, cached = adapter.lookup(name='Alex Example')
            self.assertTrue(rows[0]['stale'])
            self.assertTrue(cached)
            self.assertEqual(path, cached_path)
            fetch.assert_called_once()

    def test_identity_failures_credentials_and_rate_limits(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = PlayerNewsAdapter(SnapshotStore(root))
            with self.assertRaises(ValidationError):
                adapter.lookup(player_id=1)
            with self.assertRaises(ValidationError):
                adapter.lookup(name='Alex Example', rosters=[{'player_name':'Alex Example','player_id':p} for p in (1,2)])
        with patch.dict('os.environ', {}, clear=True), self.assertRaisesRegex(ProviderError, 'GNEWS_API_KEY'):
            fetch_news('Alex Example')
        response = Mock(status_code=429, headers={'Retry-After':'3600'})
        with patch.dict('os.environ', {'GNEWS_API_KEY':'secret-value'}), patch('src.data_collection.player_data.news.requests.get', return_value=response), self.assertRaisesRegex(ProviderError, '429') as error:
            fetch_news('Alex Example')
        self.assertNotIn('secret-value', str(error.exception))
