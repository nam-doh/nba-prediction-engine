"""Official NBA PDF reports. Omission is unknown, never confirmed availability."""
from __future__ import annotations

import base64
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import re
import time
import unicodedata
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import requests

from .contracts import ProviderError, ValidationError, parse_utc_text, utc_text
from .snapshots import SnapshotStore

HOST = 'https://ak-static.cms.nba.com'
URL_PATTERN = re.compile(r'https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf')
STATUSES = {'out', 'doubtful', 'questionable', 'probable', 'available'}
USER_AGENT = 'NBAResearchSnapshots/1.0 (private noncommercial research)'


def normalized_name(name):
    if ',' in name:
        last, first = name.split(',', 1)
        name = first + ' ' + last
    return ''.join(c for c in unicodedata.normalize('NFKD', name).casefold() if c.isalnum())


def report_time(url):
    match = URL_PATTERN.fullmatch(url)
    if not match:
        raise ValidationError('Use an exact timestamped official NBA injury PDF URL')
    date, hour, minute, ampm = match.groups()
    return datetime.strptime(f'{date} {hour}:{minute}{ampm}', '%Y-%m-%d %I:%M%p').replace(
        tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)


def fetch_pdf(url):
    """Check robots on the same host, delay, and stop on any denial/rate limit."""
    report_time(url)
    try:
        robots = requests.get(HOST + '/robots.txt', headers={'User-Agent': USER_AGENT}, timeout=30,
                              allow_redirects=False)
        if robots.status_code != 200:
            raise ProviderError(f'Robots policy unavailable: HTTP {robots.status_code}')
        policy = RobotFileParser()
        policy.parse(robots.text.splitlines())
        if not policy.can_fetch(USER_AGENT, url):
            raise ProviderError('Official host robots policy denies this report')
        time.sleep(max(3, policy.crawl_delay(USER_AGENT) or 0))
        response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=30, allow_redirects=False)
        if response.status_code != 200:
            raise ProviderError(f'Official report unavailable: HTTP {response.status_code}; '
                                f'Retry-After={response.headers.get("Retry-After", "unspecified")}')
        if not response.content.startswith(b'%PDF-'):
            raise ProviderError('Official report did not return a PDF')
        return response.content
    except requests.RequestException as exc:
        raise ProviderError('Official report network request failed; availability remains unknown') from exc


def pdf_rows(payload):
    """Extract table columns; center-aligned names anchor wrapped reason cells."""
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(payload))
    rows, context = [], ['', '', '', '']
    bounds = None
    for page_index, page in enumerate(reader.pages):
        tokens = []
        def visit(text, cm, tm, font, size):
            if text.strip():
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                y = float(page.mediabox.height) - (tm[4] * cm[1] + tm[5] * cm[3] + cm[5])
                tokens.append((round(y, 1), x, text.strip()))
        page.extract_text(visitor_text=visit)
        if page_index == 0:
            headers = {label: next(((y, x) for y, x, t in tokens if t == label), None)
                       for label in ('Matchup', 'Team', 'Player', 'Current', 'Reason')}
            if any(value is None for value in headers.values()):
                raise ValidationError('Unrecognized official PDF table headers')
            bounds = [headers[label][1] - 2 for label in ('Matchup', 'Team', 'Player', 'Current', 'Reason')]
            start_y = headers['Player'][0] + 2
        else:
            start_y = 85
        lines = {}
        end_y = min((y - 2 for y, x, text in tokens if text == 'Page' and y > 400),
                    default=float(page.mediabox.height) - 35)
        for y, x, text in sorted(tokens):
            if y <= start_y or y >= end_y:
                continue
            columns = lines.setdefault(y, [[] for _ in range(6)])
            columns[bisect_right(bounds, x)].append(text)
        anchors, reasons = [], []
        for y, columns in lines.items():
            left, matchup, team, player, status, reason = [' '.join(c) for c in columns]
            date_match = re.search(r'\d{2}/\d{2}/\d{4}', left)
            if date_match:
                context[0] = datetime.strptime(date_match[0], '%m/%d/%Y').date().isoformat()
            if left:
                context[1] = re.sub(r'\d{2}/\d{2}/\d{4}', '', left).strip() or context[1]
            if matchup:
                context[2] = matchup
            if team:
                context[3] = team
            combined = ' '.join((player, status, reason))
            if 'NOT YET SUBMITTED' in combined.upper():
                anchors.append((y, dict(game_date=context[0], game_time=context[1], matchup=context[2],
                                        team_name=context[3], player_name=None, status='unknown', reason='NOT YET SUBMITTED')))
            elif status:
                if status.casefold() not in STATUSES or not player or not all((context[0], context[2], context[3])):
                    raise ValidationError(f'Unrecognized official player row: {combined}')
                anchors.append((y, dict(game_date=context[0], game_time=context[1], matchup=context[2],
                                        team_name=context[3], player_name=player, status=status.casefold(), reason='')))
                if reason:
                    reasons.append((y, reason))
            elif player:
                raise ValidationError(f'Player row without recognized official status: page={page_index + 1}, y={y}, cells={columns}')
            elif reason:
                reasons.append((y, reason))
        for y, reason in reasons:
            if not anchors:
                raise ValidationError('Reason without a player row')
            target = min(anchors, key=lambda item: abs(item[0] - y))[1]
            target['reason'] = (target['reason'] + ' ' + reason).strip()
        rows.extend(row for _, row in anchors)
    if not rows:
        raise ValidationError('Official report contains no recognized rows; availability remains unknown')
    return rows


class AvailabilityAdapter:
    def __init__(self, store: SnapshotStore, *, fetcher=fetch_pdf, parser=pdf_rows,
                 clock=lambda: datetime.now(timezone.utc)):
        self.store, self.fetcher, self.parser, self.clock = store, fetcher, parser, clock

    def refresh(self, url, *, rosters=(), team_ids=None):
        as_of = report_time(url)
        now = self.clock()
        utc_text(now)
        if as_of > now:
            raise ValidationError('Report time is in the future')
        # Identity resolution is part of the request, so a changed roster cannot reuse old resolution.
        roster_hash = hashlib.sha256(repr(sorted((r['team_id'], r['player_id'], r['player_name']) for r in rosters)).encode()).hexdigest()
        request = {'url': url, 'roster_hash': roster_hash, 'team_ids': team_ids or {}}
        cached = self.store.latest(provider='nba_official', dataset='availability', request=request)
        if cached and timedelta(0) <= now - parse_utc_text(cached[1]['retrieved_at']) < timedelta(minutes=15):
            return cached[0], True
        payload = self.fetcher(url)
        retrieved = self.clock()
        records = self.parser(payload)
        seen = set()
        for row in records:
            row['team_id'] = (team_ids or {}).get(row['team_name'])
            candidates = {r['player_id'] for r in rosters if r['team_id'] == row['team_id']
                          and row['player_name'] and normalized_name(r['player_name']) == normalized_name(row['player_name'])}
            row['player_id'] = next(iter(candidates)) if len(candidates) == 1 else None
            row['identity_resolution'] = 'resolved' if len(candidates) == 1 else ('ambiguous' if candidates else 'unresolved')
            row['game_id'] = None  # PDFs publish matchup/date, not stable game IDs.
            row['source_url'] = url
            row['source_as_of'] = utc_text(as_of)
            row['retrieved_at'] = utc_text(retrieved)
            row['supporting_text'] = ' | '.join(str(row[k] or '') for k in ('game_date', 'matchup', 'team_name', 'player_name', 'status', 'reason'))
            identity = (row['game_date'], row['matchup'], row['team_name'], row['player_name'])
            if identity in seen:
                raise ValidationError('Duplicate official report identity')
            seen.add(identity)
        path = self.store.write(provider='nba_official', dataset='availability', request=request,
                                source_url=url, source_as_of=as_of, retrieved_at=retrieved, records=records,
                                raw_payload={'encoding': 'base64', 'pdf': base64.b64encode(payload).decode()})
        return path, False
