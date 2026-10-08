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

## T004 | pending | Verify OMP runner integration
Files: tests/test_runner.py
Acceptance: focused regression coverage proves OMP uses print mode with the
explicit provider/model and rejects a provider mismatch; record the smoke
result, model, and reported token usage in PROGRESS.md. Do not invoke workers,
advisor calls, or alter datasets, models, notebooks, or task status.
