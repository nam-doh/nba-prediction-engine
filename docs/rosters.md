# NBA roster ingestion

The roster adapter calls NBA.com's `commonteamroster` stats endpoint through
the existing `nba_api` dependency. It requires no API key and explicitly sends
league ID `00`, which current `nba_api` release notes require for this endpoint.
The default command requests the library's 30 static NBA team IDs sequentially,
waits three seconds between live successes, and reuses an exact-request
snapshot for one hour.

```bash
../../venv/bin/python -m scripts.refresh_rosters --season 2026-27
../../venv/bin/python -m scripts.refresh_rosters --season 2026-27 \
  --team-id 1610612738 --snapshot-dir /tmp/nba-player-snapshots --force
```

Each normalized record contains season, numeric NBA team/player IDs, player
name and optional slug/position/jersey, source URL, and UTC retrieval time. A
player can appear under different team IDs in snapshots before and after a
trade. Names are display fields and are never identity keys. Duplicate
`(season, team_id, player_id)` rows, missing IDs/names, empty rosters, and rows
for the wrong team fail validation.

The command prints JSON and exits nonzero if any team fails. Snapshots from
teams fetched before a later failure remain intact and are reported. A current
roster snapshot proves only observed membership at its retrieval time. It must
not be joined to games before that time or treated as a historical transaction
log. Building historical roster membership requires dated snapshots or game
logs that identify the player's team for each game.

Network-free fixtures validate the adapter. Live verification status and
provider access observations are recorded in `docs/player-data-sources.md` and
`PROGRESS.md`; do not interpret fixture success as live endpoint availability.
