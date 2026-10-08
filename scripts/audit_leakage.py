"""Read-only historical pregame audit. Prints JSON; never trains or writes data."""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATS = ('PTS', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'REB', 'AST', 'STL',
         'BLK', 'TOV', 'PLUS_MINUS')
ROLLING = {f'{c}_ROLL5': c for c in STATS} | {'WIN_PCT_ROLL5': 'WIN'}
OPPONENT = (*ROLLING, 'REST_DAYS')
DIFFERENCES = ('PTS_ROLL5', 'FG_PCT_ROLL5', 'FG3_PCT_ROLL5', 'REB_ROLL5',
               'AST_ROLL5', 'TOV_ROLL5', 'PLUS_MINUS_ROLL5',
               'WIN_PCT_ROLL5', 'REST_DAYS')
CUMULATIVE = ('PREV_WIN', 'PREV_PTS', 'PREV_WINS', 'PREV_GAMES',
              'SEASON_WIN_PCT', 'TEAM_GAME_NUMBER', 'REST_DAYS', 'WIN_STREAK')
FEATURES = (*ROLLING, *CUMULATIVE, *(f'OPP_{c}' for c in OPPONENT),
            *(f'{c}_DIFF' for c in DIFFERENCES))


def key(row):
    return tuple(str(row[c]).strip() for c in ('SEASON', 'GAME_ID', 'TEAM_ID'))


def number(value):
    if value is None or str(value).strip().lower() in ('', 'nan'):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('nonfinite number')
    return result


def equal(actual, expected):
    actual = number(actual)
    return actual is expected if actual is None or expected is None else math.isclose(
        actual, expected, rel_tol=1e-9, abs_tol=1e-9)


def audit_rows(history, modeling):
    """Reconstruct from independent historical rows, accepting unsorted input.

    Invalid structure fails closed before reconstruction. Same-day team games
    are rejected because row shifts cannot establish strictly earlier dates.
    Numeric equality requires matching missingness and 1e-9 tolerance.
    """
    issues = Counter()
    samples = []
    checks = Counter()

    def issue(kind, row=None, column=None):
        issues[kind] += 1
        if len(samples) < 20:
            samples.append({'issue': kind, 'key': key(row) if row else None,
                            'column': column})

    def index(rows, label, required):
        indexed = {}
        games = defaultdict(list)
        dates = {}
        seen_dates = set()
        if not rows:
            issue(f'{label}:empty')
        for row in rows:
            if any(c not in row for c in required):
                issue(f'{label}:missing_columns')
                continue
            if any(row[c] is None or not str(row[c]).strip()
                   for c in ('SEASON', 'GAME_ID', 'TEAM_ID')):
                issue(f'{label}:missing_identifier', row)
                continue
            k = key(row)
            if k in indexed:
                issue(f'{label}:duplicate_team_game', row)
            indexed[k] = row
            games[k[:2]].append(row)
            try:
                d = date.fromisoformat(str(row['GAME_DATE']))
                dates[k] = d
                team_date = (k[0], k[2], d)
                if team_date in seen_dates:
                    issue(f'{label}:non_strict_team_dates', row)
                seen_dates.add(team_date)
            except (ValueError, TypeError):
                issue(f'{label}:invalid_date', row)
        for rows_in_game in games.values():
            if len(rows_in_game) != 2 or len({key(r)[2] for r in rows_in_game}) != 2:
                issue(f'{label}:opponent_cardinality', rows_in_game[0])
            if len({r['GAME_DATE'] for r in rows_in_game}) != 1:
                issue(f'{label}:inconsistent_game_date', rows_in_game[0])
        return indexed, dates, games

    source, dates, games = index(history, 'history',
        ('SEASON', 'GAME_ID', 'TEAM_ID', 'GAME_DATE', 'WIN', *STATS))
    stored, _, _ = index(modeling, 'modeling',
        ('SEASON', 'GAME_ID', 'TEAM_ID', 'GAME_DATE', 'WIN', *STATS,
         'OPPONENT_TEAM_ID', *FEATURES))
    for k in source.keys() ^ stored.keys():
        issue('row_coverage', (source | stored)[k])
    for row in source.values():
        try:
            if number(row['WIN']) not in (0, 1):
                issue('invalid_target', row)
            for c in STATS:
                number(row[c])
        except (ValueError, TypeError, KeyError):
            issue('invalid_source_numeric', row)
    expected = {}
    if not issues:
        teams = defaultdict(list)
        for k, row in source.items():
            teams[(k[0], k[2])].append(row)
        for rows in teams.values():
            prior = []
            streak = 0
            for row in sorted(rows, key=lambda r: dates[key(r)]):
                k = key(row)
                n = len(prior)
                if n:
                    checks['strict_prior_date'] += 1
                values = {'PREV_WIN': number(prior[-1]['WIN']) if n else None,
                          'PREV_PTS': number(prior[-1]['PTS']) if n else None,
                          'PREV_WINS': sum(number(r['WIN']) for r in prior),
                          'PREV_GAMES': n, 'TEAM_GAME_NUMBER': n + 1,
                          'WIN_STREAK': streak,
                          'REST_DAYS': (dates[k] - dates[key(prior[-1])]).days if n else None}
                values['SEASON_WIN_PCT'] = values['PREV_WINS'] / n if n else None
                for feature, stat in ROLLING.items():
                    recent = [number(r[stat]) for r in prior[-5:]]
                    recent = [v for v in recent if v is not None]
                    values[feature] = sum(recent) / len(recent) if recent else None
                expected[k] = values
                streak = streak + 1 if number(row['WIN']) else 0
                prior.append(row)
        for k, row in stored.items():
            opponent = next(r for r in games[k[:2]] if key(r)[2] != k[2])
            opp_key = key(opponent)
            checks['opponent_cardinality'] += 1
            if str(row['OPPONENT_TEAM_ID']) != opp_key[2]:
                issue('opponent_identity', row)
            if row['GAME_DATE'] != source[k]['GAME_DATE']:
                issue('source_date_mismatch', row)
            values = expected[k].copy()
            values.update({f'OPP_{c}': expected[opp_key][c] for c in OPPONENT})
            for c in DIFFERENCES:
                a, b = values[c], values[f'OPP_{c}']
                values[f'{c}_DIFF'] = a - b if a is not None and b is not None else None
            # Also detect divergence of the exported outcomes from the source.
            values.update({c: number(source[k][c]) for c in ('WIN', *STATS)})
            for c, expected_value in values.items():
                checks[c] += 1
                try:
                    matches = equal(row[c], expected_value)
                except (ValueError, TypeError):
                    matches = False
                if not matches:
                    issue('feature_mismatch', row, c)
    return {'ok': not issues, 'history_rows': len(history), 'modeling_rows': len(modeling),
            'games': len(games), 'date_min': str(min(dates.values())) if dates else None,
            'date_max': str(max(dates.values())) if dates else None,
            'seasons': dict(sorted(Counter(str(r.get('SEASON', '')) for r in history).items())),
            'checks': dict(checks), 'issues': dict(issues), 'samples': samples}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, default=ROOT / 'data/processed/team_game_logs_clean.csv')
    parser.add_argument('--modeling', type=Path, default=ROOT / 'data/processed/team_game_modeling.csv')
    args = parser.parse_args(argv)
    try:
        rows = []
        inputs = {}
        for name, path in (('history', args.history), ('modeling', args.modeling)):
            raw = path.read_bytes()
            inputs[name] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
            with path.open(newline='') as stream:
                rows.append(list(csv.DictReader(stream)))
        report = audit_rows(*rows)
        report['inputs'] = inputs
    except (OSError, ValueError, TypeError) as exc:
        report = {'ok': False, 'error': str(exc)}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
