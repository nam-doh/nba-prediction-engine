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
