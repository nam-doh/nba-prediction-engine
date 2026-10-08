# Prioritized improvements

Machine-readable entries use `## ID | pending/done | title` followed by
`Files: path, path`. Only these files plus TASKS.md/PROGRESS.md can be staged.

## T001 | done | Add chronological partition guard
Files: src/modeling/chronological.py, tests/test_chronological.py
Acceptance: explicit date cutoffs; strict train < validation < holdout ordering;
all rows of a game and same-date games stay together; reject invalid dates,
missing IDs, inconsistent game dates, empty partitions, and reversed cutoffs.
Tests exercise unsorted paired rows and boundary failures. No model or notebook
changes; holdout is returned without fitting or scoring.

## T002 | done | Audit historical pregame leakage
Files: scripts/audit_leakage.py, tests/test_audit_leakage.py, docs/leakage-audit.md
Acceptance: read-only audit reconstructs shifted rolling and cumulative win
features from historical rows; checks opponent join cardinality and temporal
ordering; regression test deliberately contaminates a feature and detects it.
Record actual data findings, notebook split/holdout exposure, and limitations.
Do not mutate datasets or notebooks. Validation runs the audit independently.

## T003 | done | Freeze chronological evaluation protocol
Files: docs/evaluation-protocol.md, scripts/baseline.py, tests/test_baseline.py
Acceptance: record baseline on pre-2025-26 chronological train/validation dates,
with scaler fit only on train; report accuracy, AUC, log loss, Brier, feature/data
hashes and seed. Define candidate gates: lower validation log loss, Brier no
worse, AUC decrease <=0.005. Exclude exposed 2025-26 from tuning; reserve a new
future holdout explicitly and do not score it. No candidate promotion here.

## T004 | done | Verify OMP runner integration
Files: tests/test_runner.py
Acceptance: focused regression coverage proves OMP uses print mode with the
explicit provider/model and rejects a provider mismatch; record the smoke
result, model, and reported token usage in PROGRESS.md. Do not invoke workers,
advisor calls, or alter datasets, models, notebooks, or task status.

## T005 | done | Make evaluation reports reproducible
Files: scripts/evaluation_report.py, tests/test_evaluation_report.py, docs/evaluation-report.md
Acceptance: read-only CLI emits deterministic JSON containing the frozen T003
protocol ID, ordered feature hash, input data hash, seed, library versions,
partition dates/counts, and accuracy/AUC/log-loss/Brier metrics. Repeated runs
on unchanged inputs produce byte-identical output; invalid dates, IDs, missing
features, and mixed partitions fail closed. Use only the pre-2025-26 training
and 2024-25 validation intervals; do not fit, tune, or score the exposed
2025-26 period or reserved 2026-27 holdout. No dataset, notebook, or model
artifact writes.

## T006 | pending | Measure validation probability reliability
Files: scripts/reliability.py, tests/test_reliability.py, docs/reliability.md
Acceptance: validation-only report evaluates the frozen T003 baseline with
log-loss, Brier score, ROC AUC, accuracy, fixed calibration bins, sample
counts, and class prevalence. Preprocessing is fit only on training rows;
paired game rows remain together and same-date rows never cross partitions.
Tests detect future/exposed-row contamination, non-deterministic bin edges,
missing probabilities, and incomplete game pairs. No calibrator fitting,
candidate promotion, holdout scoring, dataset mutation, or production artifact
replacement.

## T007 | done | Enforce as-of pregame feature construction
Files: src/modeling/pregame_features.py, tests/test_pregame_features.py, docs/pregame-features.md
Acceptance: reusable in-memory builder computes rolling, cumulative, rest-day,
and opponent features strictly from earlier games, excludes every same-date
game, and performs one-to-one opponent joins. Tests reject duplicate/missing
opponents, out-of-order rows, current-game contamination, future-row
contamination, and season-boundary leakage; missing history is explicit rather
than filled from postgame values. No notebook, dataset, serialized-model, or
production-prediction changes; document integration points and limitations.

## T008 | done | Extract a safe reusable pregame inference API
Files: src/modeling/inference.py, tests/test_inference.py, docs/inference.md
Acceptance: expose one inference entry point used by both the interface and
tests; load the existing read-only `models/logistic_regression_production.pkl`
pipeline without fitting, retraining, calibration, replacement, or fallback
predictions. Verify that the persisted scaler/classifier pipeline accepts the
exact ordered 36-feature contract before calling `predict_proba`. Reuse
T007's as-of feature builder rather than duplicating rolling/opponent logic.
Require an explicit hypothetical game date and use only team-state and
schedule/history rows with `GAME_DATE < game_date`; same-date and future rows
must not affect state, rest, or next-game-number features. Reject identical or
unknown teams, invalid dates, missing source/model files, missing required
columns, missing/non-finite feature values, and unavailable team history with
clear exceptions; never fill those cases with dummy values. Return both
probabilities plus the source last-available date, each team state date,
rest-day values, and assumptions metadata. Probabilities must be finite,
within [0, 1], sum to 1, and identify the home/away orientation. Tests use the
real persisted model for an end-to-end known matchup and targeted pregame,
future-row, same-date, invalid-input, missing-data, and no-fit regressions.
Document that the current historical source is static and that injuries,
lineups, trades, and player availability are not modeled.

## T009 | done | Build the Streamlit matchup interface
Files: dashboards/app.py, requirements.txt
Acceptance: add Streamlit as an explicit runtime dependency and implement a
small local app that gets its team list, source date, assumptions, and
probabilities exclusively from the T008 inference API. Provide two distinct
team selectors, an explicit home-team choice, and a predict action; use a
validated hypothetical date after the data cutoff rather than silently using
the wall clock. Display each team's win probability with clear home/away
labels, the hypothetical date, source last-available date, rest calculation
assumption, static team-statistics cutoff, and an explicit missing
injury/lineup-information warning. Historical-data predictions must be
visibly labeled when current data is unavailable. Surface missing files,
unknown teams, invalid selections, and inference failures as actionable UI
errors; do not show stale `latest_predictions.csv` values, fabricate a
probability, or write model/data artifacts. The app must remain offline and
must not fetch unvalidated current data.

## T010 | done | Smoke-test and document local launch
Files: tests/test_streamlit_app.py, README.md
Acceptance: add a real Streamlit `AppTest` smoke check that launches
`dashboards/app.py`, selects two different known teams, selects the home team,
clicks predict, and asserts both rendered probabilities, metadata, and the
historical-data warning are present. Exercise an invalid/missing-input path
and assert that no probability is rendered for that request. The smoke test
uses the persisted model and repository data, performs no network calls, and
does not write datasets, models, or prediction exports; it must run with the
declared dependency rather than being silently skipped. Add copy-pasteable
from-root launch instructions (`streamlit run dashboards/app.py`), dependency
setup, and the data-cutoff/injury and lineup limitations to the README.
Run the standard unittest discovery and `scripts/validate.py` without
executing training or changing notebooks/artifacts.

## T011 | done | Document player-data source selection
Files: docs/player-data-sources.md
Depends: none.
Acceptance: compare primary documentation and observed access for current NBA
rosters/stable IDs, player game logs/season statistics, timestamped official
availability, news, and historical roster/injury backtesting. Record coverage,
freshness, historical availability, cost, authentication, published rate
limits, permitted-use constraints, source URLs, probe dates, and whether each
sample was live-verified or only fixture-tested. Select usable no-purchase
sources, document exact key setup where required, and do not claim access to an
endpoint that was not verified. Evaluate official NBA injury reports and any
robots/terms constraints; prefer structured reports over article scraping.

## T012 | done | Add immutable player-data snapshot storage
Files: .gitignore, src/__init__.py, src/data_collection/__init__.py, src/data_collection/player_data/__init__.py, src/data_collection/player_data/contracts.py, src/data_collection/player_data/snapshots.py, tests/test_player_snapshots.py, docs/player-snapshots.md
Depends: T011.
Acceptance: add normalized provenance contracts and an immutable JSON snapshot
store with UTC retrieval timestamps, provider/dataset/request metadata, source
URL, optional source-as-of time, normalized records, raw payload, content hash,
atomic writes, safe path components, deterministic serialization, and latest
snapshot lookup. Reject naive timestamps, path traversal, corrupt snapshots,
and attempted overwrite with different content. Redact common credential query
parameters from stored source URLs. Tests use only temporary directories and
perform no network, dataset, model, notebook, or production-artifact writes.

## T013 | done | Ingest current NBA rosters
Files: src/data_collection/player_data/rosters.py, scripts/refresh_rosters.py, tests/test_rosters.py, docs/rosters.md
Depends: T011, T012. Runtime dependency: existing `nba_api` package.
Acceptance: implement an injectable NBA roster adapter using stable numeric team
and player IDs, season, normalized name/position/jersey, source URL, retrieval
time, and timestamped raw-plus-normalized snapshots. Preserve separate
player-team memberships for trades, allow duplicate names, reject duplicate
identity rows and malformed required fields, and report per-team source failures
without inventing records or discarding successful snapshots. The refresh CLI
supports one or all 30 teams, defaults to a conservative inter-request delay,
keeps API keys out of Git, and exits nonzero on partial failure. Fixture tests
cover normalization, trades/names, caching, malformed responses, and failure
retention; document live-verification status and current-roster-only limits.

## T014 | done | Ingest NBA player game statistics
Files: src/data_collection/player_data/statistics.py, scripts/refresh_player_stats.py, tests/test_player_stats.py, docs/player-stats.md
Depends: T011, T012. Runtime dependency: existing `nba_api` package.
Acceptance: implement an injectable season player-game-log adapter with stable
player/team/game IDs, game date, season/type, minutes and core box-score fields,
source URL, retrieval time, and timestamped raw-plus-normalized snapshots.
Preserve traded-team IDs, allow duplicate names, reject duplicate game-player
identities, invalid dates/minutes/required IDs, and provider failures without
fallback data. The refresh CLI accepts an explicit season/type and performs no
model training. Tests are network-free fixtures and prove temporal fields,
missing optional values, validation, and immutable snapshot provenance;
document live-verification status and strict pregame-use requirements.

## T015 | done | Ingest official player availability
Files: requirements.txt, src/data_collection/player_data/availability.py, scripts/refresh_availability.py, tests/test_availability.py, docs/availability.md
Depends: T011, T012, T013. Runtime dependency: declare the selected PDF/parser package.
Acceptance: ingest timestamped official NBA injury reports from their structured
PDF publication flow, preserving report time, game/team/player IDs where
available, normalized status, reason, supporting text, source URL, retrieval
time, and raw snapshots. Missing reports remain unknown, never available.
Handle report revisions, ambiguous names, rate limits, cache hits, and source
failures. Use conservative requests, honor published terms/robots, do not bypass
controls, and add fixture tests plus an explicitly labeled live probe.

## T016 | pending | Add a provenance-safe player-news lookup
Files: src/data_collection/player_data/news.py, scripts/player_news.py, tests/test_player_news.py, docs/player-news.md
Depends: T011, T012, T013, T015. Runtime dependency: existing `requests`; optional provider key via environment only.
Acceptance: look up recent relevant items by stable player ID or normalized
name and return headline, publication time, source URL, retrieval time, and any
reported availability. Keep official statuses separate from unconfirmed news;
never infer injury from a headline or treat stale news as current. Structured
article extraction must retain supporting text, provenance, and uncertainty.
Cache conservatively, handle rate limits/source failure, keep credentials out
of Git, avoid an LLM dependency, and fixture-test all classification behavior.

## T017 | pending | Estimate interpretable player contributions
Files: src/modeling/player_contributions.py, tests/test_player_contributions.py, docs/player-contributions.md
Depends: T007, T013, T014, T015.
Acceptance: estimate expected minutes from strictly prior rotations and explicit
availability scenarios; estimate player strength from pregame historical
performance with sample-size shrinkage and recency weighting; redistribute
unavailable minutes within plausible role/position constraints; and aggregate
expected-minute-weighted team features. Missing availability stays unknown.
Prevent same-date/future leakage and current-roster historical leakage, expose
assumptions/uncertainty, and define features to minimize double counting of
existing team strength. Add focused temporal and scenario regressions.

## T018 | pending | Validate incremental player-feature value
Files: scripts/player_feature_evaluation.py, tests/test_player_feature_evaluation.py, docs/player-feature-evaluation.md
Depends: T003, T005, T006, T007, T017.
Acceptance: freeze numerical promotion criteria before fitting and compare the
existing baseline, player-stat features, then availability scenarios using
chronological development validation only. Report accuracy, ROC AUC, log loss,
Brier score, calibration, hashes, dates, seeds, and sample counts. Enforce
strict source-available-before-game joins, train-only preprocessing, paired and
same-date partitions, no current-roster retrospective joins, and no scoring or
tuning on the exposed 2025-26 period or reserved future holdout. Promote no
features or production artifact in this task.

## T019 | pending | Integrate accepted player scenarios into inference
Files: src/modeling/inference.py, src/modeling/player_inference.py, tests/test_player_inference.py, docs/inference.md
Depends: T008, T018; only accepted T018 features may be integrated.
Acceptance: extend the read-only inference API with roster contributions,
availability scenarios, source links, retrieval/source timestamps, and
stale/missing warnings while preserving the exact production artifact unless a
separately validated candidate is explicitly promoted. Make live versus
historical inputs explicit, fail closed on schema/provenance errors, keep
unknown availability uncertain, and add tests for scenario bounds, stale data,
source failures, and absence of fallback fabrication.

## T020 | pending | Show player inputs and scenarios in the UI
Files: dashboards/__init__.py, dashboards/player_panels.py, dashboards/app.py, tests/test_player_panels.py, tests/test_streamlit_app.py, README.md
Depends: T016, T019.
Acceptance: show roster contributions, player availability scenarios, official
versus unconfirmed news, source links, last-updated/source-as-of timestamps, and
stale/missing-data warnings. Clearly label live versus historical predictions
and never imply missing injury information confirms availability. AppTests cover
complete, stale, missing, and provider-failure states without network access or
artifact writes; document refresh, key setup, and local launch commands.
