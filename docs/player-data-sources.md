# Player-data source research

Research and live probes were performed on 2026-10-08. Provider terms,
pricing, quotas, schemas, and access can change; recheck the linked primary
documentation before production use. No subscription was purchased and no
trial requiring payment details was started.

## Selected sources

| Need | Selected source | Coverage and freshness | History | Cost, auth, and limits | Access verified here |
|---|---|---|---|---|---|
| Current rosters and stable IDs | NBA.com `commonteamroster` through [`nba_api`](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/commonteamroster.md) | One team/season per request; numeric NBA team and player IDs; expected to reflect the requested season's currently served roster | A season parameter exists, but the response is not a dated transaction ledger and cannot establish membership on a past game date | No key or direct charge. NBA.com publishes no endpoint quota or availability SLA. This project caches for one hour and defaults to one request every three seconds. | **Live verified.** Boston 2026-27 returned 21 rows. First normalized row contained team ID `1610612738`, player ID `201144`, and source retrieval time `2026-10-08T17:13:25.292463Z`. |
| Player game logs | NBA.com `playergamelogs` through [`nba_api`](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/playergamelogs.md) | League-wide player/game box scores for explicit season/type; one request avoids per-player fan-out | Completed seasons are queryable. Each row carries the player's team for that game, which supports trades. It does not provide the original publication time. | No key or direct charge; no published quota/SLA. This project caches an exact request for six hours. | **Live verified.** The 2025-26 regular season returned 26,651 player-game rows. The first response row retained game `0022500001`, date `2025-10-21`, player `201142`, team `1610612745`, and 47.05 minutes. |
| Official availability | NBA's timestamped [official injury-report PDF](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-04-04_12_45AM.pdf) publication flow | Structured tables contain report time, game date/time, matchup, team, player, status, and reason; reports are revised repeatedly before games | Individual historical PDFs are discoverable, but no complete public archive/index or completeness guarantee was found. Historical backtesting is therefore blocked until coverage is audited; collect snapshots going forward. | No key or direct charge found; no report-specific quota/SLA. T015 will cache immutable PDFs/parsed rows and poll conservatively rather than scrape articles. | **Live PDF verified** through the official CDN. No parser is implemented in T011-T014. |
| Player news | [GNews API documentation](https://docs.gnews.io/) as an optional T016 search feed, with official NBA statuses kept separate | Search returns headline, publication time, URL, description/content fields and supports date filters; free data is delayed 12 hours | Free archive is 30 days; paid history begins in 2020, which is still not an injury-status ledger | Free key: 100 requests/day, 10 articles/request, development/testing and non-commercial use only. Production or published commercial use requires a paid plan, which this project will not purchase. | Documentation verified; **no key was supplied and no live API response was claimed**. |

The selected ID namespace is NBA.com's numeric IDs. Other provider IDs must be
kept in an explicit crosswalk with provider and observation time; they must
never silently replace NBA IDs. Names remain display/search fields because
duplicate and changing names are possible.

NBA.com does not publish an API contract for the stats endpoints. The
third-party `nba_api` package is MIT licensed, but that license does not grant
rights to NBA data. NBA.com's [Terms of Use](https://www.nba.com/termsofuse)
describe statistics and other basketball material as Basketball Content,
allow personal non-commercial downloads, and require permission for public or
commercial reuse. Do not commit or redistribute raw NBA snapshots. The
[NBA.com robots file](https://www.nba.com/robots.txt) disallows `/api/*` for the
general agent and blocks several named AI agents; the selected stats host uses
`stats.nba.com/stats/...`, while injury PDFs use `ak-static.cms.nba.com`.
Robots rules are not a license. T015 must recheck the applicable host rules and
terms before automating report retrieval and must stop rather than bypass an
access control.

## Alternatives evaluated

| Source | Useful coverage | Freshness/history | Cost/rate/auth | Decision |
|---|---|---|---|---|
| [BALLDONTLIE NBA API](https://docs.balldontlie.io/) | Stable provider-specific team/player IDs; games are on the free tier. Player game stats and injuries are documented endpoints. | Documentation says the overall database covers 1946-current and games can be real time. The injury endpoint exposes current injury descriptions/status but documents no timestamp or historical filter. | API key required. Free is 5 requests/minute, but game-player stats, active players, and injuries require paid tiers. | Rejected for T013-T015 because the required stats/injury coverage is not free. No key was created and no endpoint response was claimed. |
| [TheSportsDB v1](https://www.thesportsdb.com/docs_api_guide.php) | Team/player/event lookup with provider-specific IDs and a public test key | Coverage varies by method; free results are capped and are not an NBA injury history | Public key `123`; 30 requests/minute documented for free users. V2 and larger limits are premium. | Live sample returned only 10 NBA teams (first: Atlanta Hawks, ID `134880`), so it is incomplete for 30-team roster ingestion. Rejected as the primary source. |
| Sportradar NBA API | Commercial schedules, rosters, statistics, injuries, and IDs | Vendor product advertises broad live/historical coverage | Contract/key required; this repository has no entitlement and no sample was accessible | Rejected: no purchase and no verified access. An adapter or endpoint is not fabricated. |
| SportsDataIO NBA API | Commercial player/game/team feeds including injuries/news | Vendor product advertises live and historical feeds, dependent on subscription | Key and paid coverage required; no repository entitlement | Rejected: no purchase and no verified access. |
| Team pages, search results, and article HTML scraping | May mention transactions or injuries | Publication times and wording vary; headlines alone are not status evidence | Fragile HTML, site-specific terms/robots, and high provenance risk | Rejected. T016 will use a structured search feed and preserve URLs/supporting text; official reports remain authoritative. |

## Credentials and refresh setup

T011-T014 require no key. Use the existing protected interpreter and write
runtime snapshots to an ignored location:

```bash
../../venv/bin/python -m scripts.refresh_rosters \
  --season 2026-27 --snapshot-dir data/snapshots/player_data
../../venv/bin/python -m scripts.refresh_player_stats \
  --season 2025-26 --season-type "Regular Season" \
  --snapshot-dir data/snapshots/player_data
```

For the future optional news adapter, create a free GNews account, verify the
email address, copy the dashboard key, and supply it only through the process
environment:

```bash
export GNEWS_API_KEY='replace-with-dashboard-key'
```

Never put the key in a URL saved to logs, `TASKS.md`, fixtures, snapshots, or
Git. The snapshot layer redacts common key query parameters as a second line of
defense.

## Backtesting boundary

The live roster probe is evidence only for the retrieval time, not for any
earlier game. The 2025-26 game-log probe contains historical performance and
the team recorded on each completed game, but no pregame injury state. The
official injury-report sample proves that a specific PDF exists, not that every
report needed for a historical interval is recoverable. Until a completeness
audit succeeds, availability features cannot be backfilled. T015 should collect
timestamped revisions going forward, and T017/T018 must leave unavailable
history missing rather than infer health from minutes, roster presence, or
absence of news.
