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

## T007 | pending | Enforce as-of pregame feature construction
Files: src/modeling/pregame_features.py, tests/test_pregame_features.py, docs/pregame-features.md
Acceptance: reusable in-memory builder computes rolling, cumulative, rest-day,
and opponent features strictly from earlier games, excludes every same-date
game, and performs one-to-one opponent joins. Tests reject duplicate/missing
opponents, out-of-order rows, current-game contamination, future-row
contamination, and season-boundary leakage; missing history is explicit rather
than filled from postgame values. No notebook, dataset, serialized-model, or
production-prediction changes; document integration points and limitations.

## T008 | pending | Extract a safe reusable pregame inference API
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
