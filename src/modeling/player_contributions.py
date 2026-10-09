"""Interpretable rotation scenarios, not calibrated win-probability adjustments."""
from datetime import datetime, timedelta
import math

from src.data_collection.player_data.contracts import ValidationError, parse_utc_text, require_positive_int
from src.data_collection.player_data.snapshots import redact_source_url

FEATURES = ('rotation_strength_spread', 'rotation_strength_delta', 'unavailable_minutes_fraction', 'unallocated_minutes_fraction')


def before_game(document, dataset, cutoff):
    if not isinstance(document, dict) or document.get('dataset') != dataset:
        raise ValidationError(f'Expected {dataset} snapshot')
    retrieved = parse_utc_text(document.get('retrieved_at'), 'retrieved_at')
    source = parse_utc_text(document['source_as_of']) if document.get('source_as_of') else retrieved
    if retrieved >= cutoff or source >= cutoff or source > retrieved:
        raise ValidationError(f'{dataset} was not available strictly before the game')
    redact_source_url(document.get('source_url'))
    if not isinstance(document.get('records'), list):
        raise ValidationError('Snapshot records must be a list')
    for row in document['records']:
        if row.get('retrieved_at') != document['retrieved_at']:
            raise ValidationError('Record and snapshot retrieval provenance disagree')
    return retrieved


def _number(value, label):
    if isinstance(value, bool):
        raise ValidationError(f'{label} must be finite numeric data')
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'{label} must be finite numeric data') from exc
    if not math.isfinite(value):
        raise ValidationError(f'{label} must be finite numeric data')
    return value


def _roles(position):
    return set(str(position or '').upper().replace('-', '').replace('/', '')) & set('GFC')


def estimate_contributions(*, roster, statistics, availability=None, team_id, game_time, scenarios=None):
    """All inputs are verified snapshot documents; membership is observed, never backfilled."""
    cutoff = parse_utc_text(game_time, 'game_time')
    team_id = require_positive_int(team_id, 'team_id')
    roster_time = before_game(roster, 'team_rosters', cutoff)
    stats_time = before_game(statistics, 'player_game_logs', cutoff)
    if roster.get('provider') != 'nba_stats' or statistics.get('provider') != 'nba_stats':
        raise ValidationError('Expected NBA statistics/roster providers')
    if availability is not None:
        before_game(availability, 'availability', cutoff)
        if availability.get('provider') != 'nba_official':
            raise ValidationError('Only official reports may supply official availability')
    scenarios = scenarios or {}
    members = [r for r in roster['records'] if r['team_id'] == team_id]
    ids = [require_positive_int(r['player_id'], 'player_id') for r in members]
    if not members or len(ids) != len(set(ids)):
        raise ValidationError('Roster must contain unique players for the selected team')
    if set(scenarios) - set(ids):
        raise ValidationError('Scenario names an unknown roster player')
    factors = {p: _number(value, 'scenario fraction') for p, value in scenarios.items()}
    if any(not 0 <= value <= 1 for value in factors.values()):
        raise ValidationError('Scenario fractions must be between 0 and 1')
    year = cutoff.year if cutoff.month >= 7 else cutoff.year - 1
    season = f'{year}-{str(year+1)[-2:]}'
    if any(r.get('season') != season for r in members):
        raise ValidationError('Roster season does not match hypothetical game season')
    logs, identities = [], set()
    for row in statistics['records']:
        date = datetime.fromisoformat(row['game_date']).date()
        # Strict calendar-date exclusion even when a tipoff time is supplied.
        if date >= cutoff.date() or row.get('season') != season or row['team_id'] != team_id:
            continue
        identity = (row['game_id'], row['player_id'])
        if identity in identities:
            raise ValidationError('Duplicate player/game statistics')
        identities.add(identity)
        minutes = _number(row['minutes'], 'minutes')
        if not 0 <= minutes <= 70:
            raise ValidationError('Implausible observed minutes')
        logs.append(row)
    if not logs:
        raise ValidationError('No strictly prior same-season rotations for this team')
    games = sorted({(r['game_date'], r['game_id']) for r in logs})[-10:]
    game_ids = {g[1] for g in games}
    recent = [r for r in logs if r['game_id'] in game_ids]
    # Transparent box-score production proxy, not causal plus/minus or player WAR.
    def production(r):
        return sum(_number(r.get(k), k) * weight for k, weight in (
            ('points', 1), ('rebounds', .7), ('assists', .7), ('steals', 1), ('blocks', 1), ('turnovers', -1)))
    weighted = [(r, .5 ** ((cutoff.date() - datetime.fromisoformat(r['game_date']).date()).days / 30)) for r in logs]
    total_minutes = sum(float(r['minutes']) * w for r, w in weighted)
    if total_minutes <= 0:
        raise ValidationError('No observed rotation minutes')
    team_rate = sum(production(r) * w for r, w in weighted) / total_minutes
    official = {}
    if availability:
        for row in availability['records']:
            if row.get('team_id') != team_id or row.get('game_date') != cutoff.date().isoformat() or row.get('player_id') is None:
                continue
            player = row['player_id']
            if player in official:
                raise ValidationError('Duplicate official player availability')
            if row['status'] not in {'available','out','doubtful','questionable','probable','unknown'}:
                raise ValidationError('Unknown official status schema')
            official[player] = row['status']
    players = []
    for member in members:
        player = member['player_id']
        baseline = min(48., sum(float(r['minutes']) for r in recent if r['player_id'] == player) / len(games))
        samples = [(r,w) for r,w in weighted if r['player_id'] == player]
        minutes = sum(float(r['minutes']) * w for r,w in samples)
        strength = ((sum(production(r) * w for r,w in samples) + 300 * team_rate) / (minutes + 300)) if samples else None
        status = official.get(player, 'unknown')
        # Uncertain statuses retain the observed rotation as an explicitly conditional scenario.
        factor = factors.get(player, 0. if status == 'out' else 1.)
        players.append({'player_id': player, 'player_name': member['player_name'], 'position': member.get('position'),
                        'official_status': status, 'scenario_fraction': factor, 'scenario_override': player in factors,
                        'baseline_minutes': baseline, 'expected_minutes': baseline * factor,
                        'strength': strength, 'weighted_sample_minutes': minutes,
                        'availability_uncertain': status not in {'out', 'available'},
                        'history_missing': not samples})
    # Remove overtime inflation without inventing minutes for absent roster members.
    total = sum(p['baseline_minutes'] for p in players)
    if total > 240:
        for player in players:
            player['baseline_minutes'] *= 240 / total
            player['expected_minutes'] = player['baseline_minutes'] * player['scenario_fraction']
    unavailable = sum(p['baseline_minutes'] - p['expected_minutes'] for p in players)
    unallocated = 0.
    for absent in players:
        lost = absent['baseline_minutes'] * (1 - absent['scenario_fraction'])
        peers = [p for p in players if p is not absent and p['scenario_fraction'] == 1 and p['strength'] is not None
                 and _roles(p['position']) & _roles(absent['position'])]
        while lost > 1e-9:
            eligible = [p for p in peers if p['expected_minutes'] < min(48., p['baseline_minutes'] + 12) - 1e-9]
            if not eligible:
                break
            share = lost / len(eligible)
            for peer in eligible:
                added = min(share, min(48., peer['baseline_minutes'] + 12) - peer['expected_minutes'])
                peer['expected_minutes'] += added
                lost -= added
        unallocated += lost
    delta = sum((p['expected_minutes'] - p['baseline_minutes']) * (p['strength'] - team_rate)
                for p in players if p['strength'] is not None) / 240
    spread = sum(p['baseline_minutes'] * (p['strength'] - team_rate) ** 2
                 for p in players if p['strength'] is not None) / 240
    warnings = ['Scenario analysis only; no validated probability adjustment.',
                'Unknown/questionable/probable status does not confirm availability; rotation continuation is conditional.',
                'Strength is a shrunk box-score proxy, not causal player impact.']
    if cutoff - roster_time > timedelta(hours=24):
        warnings.append('Stale roster snapshot: membership may have changed.')
    if cutoff - stats_time > timedelta(hours=24):
        warnings.append('Stale statistics snapshot.')
    if availability is None:
        warnings.append('Official availability missing; all unreported players remain unknown.')
    features = dict(zip(FEATURES, (spread, delta, unavailable / 240, unallocated / 240)))
    return {'team_id': team_id, 'game_time': game_time, 'mode': 'scenario_only', 'players': players,
            'features': features, 'unknown_minutes': sum(p['expected_minutes'] for p in players if p['availability_uncertain']),
            'unallocated_minutes': unallocated, 'rotation_coverage_minutes': sum(p['baseline_minutes'] for p in players),
            'warnings': warnings, 'sources': [{k:d.get(k) for k in ('provider','dataset','source_url','retrieved_at','source_as_of','content_sha256')}
                                             for d in (roster, statistics, availability) if d is not None]}
