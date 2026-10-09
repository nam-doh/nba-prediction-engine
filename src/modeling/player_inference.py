"""Read-only player context, explicitly separate from production probabilities."""
from datetime import timedelta

from src.data_collection.player_data.contracts import ValidationError, parse_utc_text
from src.modeling.player_contributions import before_game, estimate_contributions


class PlayerContextError(ValueError):
    """A local source cannot safely support the requested player context."""


def _documents(store, provider, dataset, cutoff):
    documents = []
    directory = store.root / provider / dataset
    for path in directory.glob('*/*/*/*.json'):
        document = store.read(path)  # Hash verification precedes any use.
        retrieved = parse_utc_text(document['retrieved_at'])
        source = parse_utc_text(document['source_as_of']) if document.get('source_as_of') else retrieved
        if source > retrieved:
            raise ValidationError('Source-as-of is later than retrieval')
        if retrieved < cutoff and source < cutoff:
            before_game(document, dataset, cutoff)
            documents.append(document)
    return sorted(documents, key=lambda d: (d.get('source_as_of') or d['retrieved_at'], d['retrieved_at'], d['content_sha256']), reverse=True)


def player_context(store, *, team_id, game_time, observed_at, scenarios=None):
    """No network, fitting or probability adjustment. Current rosters cannot backfill."""
    try:
        game = parse_utc_text(game_time, 'game_time')
        observed = parse_utc_text(observed_at, 'observed_at')
        cutoff = min(game, observed)
        year = game.year if game.month >= 7 else game.year-1
        season = f'{year}-{str(year+1)[-2:]}'
        rosters = _documents(store, 'nba_stats', 'team_rosters', cutoff)
        roster = next((d for d in rosters if d['request'].get('team_id') == team_id and d['request'].get('season') == season), None)
        stats = _documents(store, 'nba_stats', 'player_game_logs', cutoff)
        statistics = next((d for d in stats if d['request'].get('season') == season and d['request'].get('season_type') == 'Regular Season'), None)
        reports = _documents(store, 'nba_official', 'availability', cutoff)
        report = next((d for d in reports if any(r.get('team_id') == team_id and r.get('game_date') == game.date().isoformat() for r in d['records'])), None)
        warnings, sources = [], []
        if roster is None:
            warnings.append('Missing pregame roster snapshot; availability unknown, contributions unavailable.')
        if statistics is None:
            warnings.append('Missing prior same-season player statistics; contributions unavailable.')
        if report is None:
            warnings.append('Missing official game-specific report; missing does not mean available.')
        for document in (roster, statistics, report):
            if document:
                sources.append({key: document.get(key) for key in ('provider','dataset','source_url','retrieved_at','source_as_of','content_sha256')})
        stale_roster = roster is not None and observed - parse_utc_text(roster['retrieved_at']) > timedelta(hours=24)
        stale_report = report is not None and observed - parse_utc_text(report['source_as_of']) > timedelta(hours=6)
        if stale_roster:
            warnings.append('Stale roster: membership is observed historically, not confirmed current.')
        if stale_report:
            warnings.append('Stale official report: reported statuses shown for provenance, effective availability unknown.')
        members = roster['records'] if roster else []
        players = []
        for member in members:
            if member['team_id'] != team_id:
                raise ValidationError('Roster snapshot contains a different team')
            matches = [r for r in (report['records'] if report else []) if r.get('team_id') == team_id
                       and r.get('game_date') == game.date().isoformat() and r.get('player_id') == member['player_id']]
            if len(matches) > 1:
                raise ValidationError('Duplicate official player status')
            record = matches[0] if matches else None
            status = record['status'] if record else 'unknown'
            if status not in {'unknown','available','out','doubtful','questionable','probable'}:
                raise ValidationError('Invalid official status')
            players.append({**member, 'reported_status': status,
                            'availability': 'unknown' if stale_report else status,
                            'official_source_url': record['source_url'] if record else None,
                            'official_source_as_of': record['source_as_of'] if record else None,
                            'reason': record.get('reason') if record else None})
        contribution = None
        if roster and statistics:
            contribution = estimate_contributions(roster=roster, statistics=statistics,
                                                   availability=None if stale_report else report,
                                                   team_id=team_id, game_time=game_time, scenarios=scenarios)
            warnings.extend(contribution['warnings'])
        elif scenarios:
            raise ValidationError('Cannot apply a scenario without roster and rotation history')
        news, seen = [], set()
        identities = {p['player_id'] for p in players}
        names = {p['player_name'].casefold() for p in players}
        for document in _documents(store, 'gnews', 'player_news', cutoff):
            for row in document['records']:
                if row.get('player_id') not in identities and row.get('player_name','').casefold() not in names:
                    continue
                published = parse_utc_text(row['published_at'])
                if published >= cutoff or published > parse_utc_text(row['retrieved_at']):
                    raise ValidationError('News publication violates pregame provenance')
                if row.get('official') is not False:
                    raise ValidationError('News cannot be classified as official availability')
                if row['source_url'] in seen:
                    continue
                seen.add(row['source_url'])
                news.append({**row, 'stale': observed-published > timedelta(hours=24), 'current_availability':None})
        return {'team_id':team_id, 'game_time':game_time, 'observed_at':observed_at,
                'mode':'historical' if game <= observed else 'prospective_snapshot_scenario',
                'players':players, 'contribution':contribution, 'news':news, 'sources':sources,
                'warnings':warnings, 'production_features_accepted':False,
                'probability_adjustment':None, 'promotion_blocker':'T018 has no validated historical player-feature result.'}
    except Exception as exc:
        raise PlayerContextError(f'Player source unavailable: {exc}') from exc
