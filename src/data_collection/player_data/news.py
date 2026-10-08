"""Optional structured GNews lookup; article claims are never official statuses."""
from datetime import datetime, timedelta, timezone
import os
import re

import requests

from .availability import normalized_name
from .contracts import ProviderError, ValidationError, parse_utc_text, require_positive_int, require_text, utc_text
from .snapshots import redact_source_url

ENDPOINT = 'https://gnews.io/api/v4/search'


def reported_status(name, text):
    """Deliberately narrow explicit assertions in body sentences, not headlines."""
    statuses = set()
    support = []
    for sentence in re.split(r'(?<=[.!?])\s+|\n', text):
        match = re.fullmatch(re.escape(name) + r' (?:is|has been) (?:listed as|ruled) '
                             r'(out|doubtful|questionable|probable|available)(?: for (?:tonight|today|the game))?[.!]?',
                             sentence.strip(), flags=re.IGNORECASE)
        if match:
            statuses.add(match[1].lower())
            support.append(sentence)
    return (next(iter(statuses)) if len(statuses) == 1 else None), support


def fetch_news(name):
    key = os.environ.get('GNEWS_API_KEY')
    if not key:
        raise ProviderError('Set GNEWS_API_KEY in the process environment for optional news lookup')
    try:
        response = requests.get(ENDPOINT, params={'q': f'"{name}" NBA', 'lang': 'en', 'max': 10,
                                                 'sortby': 'publishedAt', 'apikey': key},
                                timeout=30, allow_redirects=False)
        if response.status_code != 200:
            raise ProviderError(f'News provider HTTP {response.status_code}; '
                                f'Retry-After={response.headers.get("Retry-After", "unspecified")}')
        return response.json()
    except (requests.RequestException, ValueError):
        # Never include the request URL or exception text: it may contain the key.
        raise ProviderError('News request failed; no availability inferred') from None


class PlayerNewsAdapter:
    def __init__(self, store, *, fetcher=fetch_news, clock=lambda: datetime.now(timezone.utc)):
        self.store, self.fetcher, self.clock = store, fetcher, clock

    def lookup(self, *, player_id=None, name=None, rosters=()):
        if player_id is not None:
            player_id = require_positive_int(player_id, 'player_id')
            names = {r['player_name'] for r in rosters if r['player_id'] == player_id}
            if len(names) != 1:
                raise ValidationError('Stable player ID needs exactly one name in the supplied roster snapshots')
            name = next(iter(names))
        else:
            name = require_text(name, 'player name')
            matches = {r['player_id'] for r in rosters if normalized_name(r['player_name']) == normalized_name(name)}
            if len(matches) > 1:
                raise ValidationError('Ambiguous player name; use a stable player ID')
            player_id = next(iter(matches)) if matches else None
        # Do not permit query language supplied through names.
        if not re.fullmatch(r"[\w .,'’-]+", name) or len(name) > 100:
            raise ValidationError('Invalid player search name')
        now = self.clock()
        utc_text(now)
        request = {'player_id': player_id, 'name': name}
        cached = self.store.latest(provider='gnews', dataset='player_news', request=request)
        if cached and timedelta(0) <= now - parse_utc_text(cached[1]['retrieved_at']) < timedelta(hours=6):
            return self._view(cached[1]['records'], now), cached[0], True
        payload = self.fetcher(name)
        retrieved = self.clock()
        if not isinstance(payload, dict) or not isinstance(payload.get('articles'), list):
            raise ValidationError('News response must contain an articles list')
        records, urls = [], set()
        for article in payload['articles']:
            headline = require_text(article.get('title'), 'headline')
            publication = parse_utc_text(article.get('publishedAt'), 'publication time')
            body = '\n'.join(str(article.get(field) or '') for field in ('description', 'content'))
            # Full-name word boundaries, not surname or substring relevance.
            if not re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', headline + ' ' + body, re.IGNORECASE):
                continue
            if publication > retrieved or retrieved - publication > timedelta(days=30):
                continue
            url = redact_source_url(require_text(article.get('url'), 'article URL'))
            if url in urls:
                continue
            urls.add(url)
            status, support = reported_status(name, body)
            records.append({'player_id': player_id, 'player_name': name, 'headline': headline,
                            'published_at': utc_text(publication), 'source_url': url,
                            'retrieved_at': utc_text(retrieved), 'supporting_text': body,
                            'status_support': support, 'reported_availability': status,
                            'official': False, 'uncertainty': 'Unconfirmed article claim; not an official game-specific report'})
        records.sort(key=lambda r: (r['published_at'], r['source_url']), reverse=True)
        path = self.store.write(provider='gnews', dataset='player_news', request=request, source_url=ENDPOINT,
                                retrieved_at=retrieved, records=records, raw_payload=payload)
        return self._view(records, retrieved), path, False

    @staticmethod
    def _view(records, now):
        # Age at consumption, not only ingestion; stale articles cannot look current on cache hits.
        return [{**r, 'stale': now - parse_utc_text(r['published_at']) > timedelta(hours=24),
                 'current_availability': None} for r in records]
