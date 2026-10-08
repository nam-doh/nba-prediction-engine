# Optional player news

`GNEWS_API_KEY` is read only from the process environment. Create a GNews account,
verify email and copy the dashboard key; do not put it in Git or shell scripts.
Use `python -m scripts.player_news --name 'Jayson Tatum'` or `--player-id 1628369
--roster-snapshot PATH` with a verified roster under the selected `--snapshot-dir`.
A stable ID resolves through roster names; duplicate-name IDs fail closed.

The [GNews structured search API](https://docs.gnews.io/) supplies headlines,
publication timestamps, URLs and body excerpts. The free plan is delayed 12 hours,
100 requests/day and 30 days history, for development/private noncommercial use.
This adapter caches each identity for six hours, requests at most ten results,
does not retry 429s, and never scrapes linked articles. No key was available for a
live response probe; fixtures and the actual cached CLI path were exercised.

Headlines do not establish injury. Only narrowly matched explicit full-name body
assertions (`NAME is listed as STATUS`, `NAME has been ruled out`) are extracted;
negation, questions, speculative wording and conflicting assertions remain
unclassified. The supporting body and matched sentences are retained. Unsupported
wording is deliberately unknown, not an NLP guess. Every claim remains
**unconfirmed**, never merged with official reports, and `current_availability`
is always null. Publication older than 24 hours is marked stale at consumption,
including cache hits. Future publications and items older than 30 days are excluded.

Snapshot provenance includes query identity, retrieval time, article source and
publication time, raw response and hash. A missing key/provider failure reports an
error and unknown availability, with no fabricated item. No model/holdout changes.
