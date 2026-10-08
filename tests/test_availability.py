from datetime import datetime, timedelta, timezone
from io import BytesIO
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.data_collection.player_data.availability import AvailabilityAdapter, fetch_pdf, pdf_rows, report_time
from src.data_collection.player_data.contracts import ProviderError, ValidationError
from src.data_collection.player_data.snapshots import SnapshotStore

URL = 'https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-04-04_12_45AM.pdf'
NOW = datetime(2026, 4, 4, 5, tzinfo=timezone.utc)


def fixture_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=842, height=595)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    texts = [(200,480,'Matchup'), (264,480,'Team'), (425,480,'Player'), (586,480,'Current'), (666,480,'Reason'),
             (24,450,'04/04/2026'), (200,450,'BOS@DEN'), (264,450,'Boston Celtics'),
             (425,450,'Example, Alex'), (586,450,'Out'), (666,450,'Injury/Illness'),
             (666,435,'Left knee'), (425,415,'Other, Pat'), (586,415,'Available'), (666,415,'Recovered')]
    stream = DecodedStreamObject()
    stream.set_data('\n'.join(f'q 1 0 0 1 {x} {y} cm BT /F1 10 Tf 0 0 Td ({text}) Tj ET Q' for x,y,text in texts).encode())
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class AvailabilityTests(unittest.TestCase):
    def test_pdf_columns_wrapping_and_explicit_status(self):
        rows = pdf_rows(fixture_pdf())
        self.assertEqual([r['status'] for r in rows], ['out', 'available'])
        self.assertEqual(rows[0]['reason'], 'Injury/Illness Left knee')
        self.assertEqual(rows[1]['game_date'], '2026-04-04')
        self.assertEqual(report_time(URL).hour, 4)

    def test_snapshots_cache_revisions_and_ambiguous_identity(self):
        with tempfile.TemporaryDirectory() as root:
            store = SnapshotStore(root)
            fetch = Mock(return_value=fixture_pdf())
            clock = Mock(return_value=NOW)
            adapter = AvailabilityAdapter(store, fetcher=fetch, clock=clock)
            roster = [{'player_id': p, 'team_id': 1, 'player_name': 'Alex Example'} for p in (2,3)]
            path, cached = adapter.refresh(URL, rosters=roster, team_ids={'Boston Celtics': 1})
            self.assertFalse(cached)
            document = store.read(path)
            self.assertIsNone(document['records'][0]['player_id'])
            self.assertEqual(document['records'][0]['identity_resolution'], 'ambiguous')
            self.assertEqual(document['records'][0]['source_as_of'], document['source_as_of'])
            self.assertTrue(adapter.refresh(URL, rosters=roster, team_ids={'Boston Celtics': 1})[1])
            fetch.assert_called_once()
            clock.return_value += timedelta(minutes=16)
            revised, _ = adapter.refresh(URL, rosters=roster, team_ids={'Boston Celtics': 1})
            self.assertNotEqual(path, revised)
            self.assertEqual(store.read(path), document)

    def test_denials_and_source_failure_do_not_fabricate(self):
        robots = Mock(status_code=200, text='User-agent: *\nDisallow: /')
        with patch('src.data_collection.player_data.availability.requests.get', return_value=robots), self.assertRaises(ProviderError):
            fetch_pdf(URL)
        robots.text = 'User-agent: *\nAllow: /'
        limited = Mock(status_code=429, headers={'Retry-After':'60'})
        with patch('src.data_collection.player_data.availability.requests.get', side_effect=[robots, limited]), patch('src.data_collection.player_data.availability.time.sleep'), self.assertRaisesRegex(ProviderError, '429'):
            fetch_pdf(URL)
        with tempfile.TemporaryDirectory() as root:
            store = SnapshotStore(root)
            adapter = AvailabilityAdapter(store, fetcher=Mock(side_effect=ProviderError('404')), clock=lambda: NOW)
            with self.assertRaises(ProviderError):
                adapter.refresh(URL)
            self.assertIsNone(store.latest(provider='nba_official', dataset='availability'))
        with self.assertRaises(ValidationError):
            report_time('https://example.com/report.pdf')
