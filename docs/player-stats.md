# NBA player game-log ingestion

The statistics adapter calls NBA.com's league-wide `playergamelogs` endpoint
through the existing `nba_api` dependency. One request returns player-game rows
for an explicit season and season type, minimizing request volume. No API key
is required. Exact-request snapshots are reused for six hours by default.

```bash
../../venv/bin/python -m scripts.refresh_player_stats \
  --season 2025-26 --season-type "Regular Season"
../../venv/bin/python -m scripts.refresh_player_stats \
  --season 2025-26 --snapshot-dir /tmp/nba-player-snapshots --force
```

Normalized rows retain NBA season, season type, game ID as text (including
leading zeros), ISO game date, numeric player/team IDs, display names, matchup,
win/loss, minutes, core box-score totals, source URL, and UTC retrieval time.
Optional box-score values may be null; required identity, date, team/name, and
minutes fields may not. Duplicate `(game_id, player_id)` rows, negative minutes,
non-finite numbers, malformed dates, and season mismatches fail closed.

The team ID on each historical game row is the usable evidence for that
player's team in that game, including trades. A current roster must never be
applied retrospectively. A feature for a game on date `D` may use only earlier
completed games (`game_date < D`) from a snapshot retrieved before the feature
was produced. Same-date games are one temporal partition. Retrieval time is
not a provider publication timestamp, and the endpoint supplies no injury or
availability history.

Network-free fixtures validate the adapter. Live verification status and
provider access observations are recorded in `docs/player-data-sources.md` and
`PROGRESS.md`; fixture success does not establish live endpoint availability.
