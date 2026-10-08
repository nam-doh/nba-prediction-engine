# Official availability snapshots

Run `python -m scripts.refresh_availability --url "$NBA_REPORT_URL"` with an exact
published NBA PDF URL, optionally repeating `--roster-snapshot PATH` for verified
snapshots under `--snapshot-dir data/snapshots/player_data`. Use the isolated UI
interpreter with `pypdf==6.1.1` and the existing `nba_api` dependency installed.
No key is required. No date/URL enumeration or automatic polling is performed.

The adapter checks [host robots](https://ak-static.cms.nba.com/robots.txt), waits
at least three seconds (published crawl delay: one second), disables redirects,
and stops on denials, 429, network errors or unrecognized PDF rows. Recheck
[NBA terms](https://www.nba.com/termsofuse): private noncommercial research only;
no public redistribution, gambling use or deployment is authorized. Robots is not
a license. Unknown report schemas fail rather than silently dropping players.

Column coordinates from the first-page table header carry across continuation
pages. Center-aligned status rows anchor wrapped reasons. Report filename time is
America/New_York converted to UTC; retrieval is separate. Raw PDF bytes are stored
base64 in immutable hashed snapshots. A 15-minute exact-request cache avoids
repeat requests; later retrievals/revisions create new snapshots, never overwrite.
The PDF has no stable game/player IDs: game ID stays null; team IDs use NBA's static
mapping and player IDs resolve only unique normalized name/team roster matches.
Ambiguous/unmatched names stay unresolved. Current roster resolution is not proof
of past membership and must never authorize a retrospective join.

An omitted player/report or NOT YET SUBMITTED team is **unknown**, not available.
Only an explicit Available row confirms the report's stated availability. Status
is game-specific, not a diagnosis or guarantee of minutes. Keep publication AND
retrieval strictly before a prediction cutoff; late-collected historical PDFs
cannot be used as if observed before their games.

## Verification and limits

Live probe on 2026-10-08: the [April 4 00:45 ET report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-04-04_12_45AM.pdf)
returned HTTP 200, 68,500 bytes. Parsing yielded 51 rows including 23 unknown
team submissions. Wrapped reasons and three-page context were inspected; the
retrieved payload was snapshotted under `/tmp/nba-official-live-probe`, then an
exact-request cache hit was observed. Synthetic PDF fixtures exercise extraction,
ambiguity, revisions, denials, rate limits and no-fallback failures.

No complete historical injury archive is available. Search found no indexed
October 8 report; no current report URL is invented. Prospective collection is
ready for explicitly published reports, but this historical access probe is not
prospective injury coverage or backtesting evidence. No production features change.
