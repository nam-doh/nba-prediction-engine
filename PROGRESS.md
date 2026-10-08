# Improvement results

## Initial inspection — 2026-10-07
- Branch: rerun-notebooks. Origin: nam-doh/nba-prediction-engine.
- Preserved dirty notebook 06_live_prediction_pipline.ipynb and untracked
  notebooks/05_game_simulation 2.html; neither belongs to automation.
- Existing venv: Python 3.13.9, pandas 3.0.5, sklearn 1.9.0.
  requirements.txt pins different installed package versions; no reinstall.
- No existing tests or packaged CLI training pipeline. Training is notebook-led.
- Notebook 03 shifts rolling values, subtracts current win from cumulative wins,
  joins opponent pregame features and holds out season 2025-26. Repeated model
  comparisons expose that season; it cannot be described as untouched.
- Notebook 06 fits a production model; it is user-dirty and was not executed.
- Existing datasets and production pickle are tracked already. Ignore rules
  prevent new artifacts; no existing artifacts or history were removed.
- First bounded improvement is infrastructure for safe chronological partitions;
  it changes no model, so model baseline/promotion criteria do not apply.

## T001 — completed
- Added explicit chronological split utility with inclusive validation/holdout
  start dates and fail-closed input checks. Unsorted paired game rows and all
  same-date games stay in one partition. Returned copies preserve source data.
- Eight focused tests pass (three split regressions, five runner checks).
  Offline Python syntax and notebook structure validation passes.
- Dry run passed without agent execution, Git mutation, commits, or pushes.
  Logs: .automation/logs/20261007-234931-24706/.
- No model training, evaluation, or production artifact changes. Existing
  notebook consumers are unchanged; adoption is a later scoped task.

## T002 — audit implementation and acceptance evidence — 2026-10-08
- Added read-only `scripts/audit_leakage.py`, seven focused regression tests,
  and `docs/leakage-audit.md`. Only the four authorized files were edited;
  TASKS.md remains unchanged for runner adjudication. No Git mutations.
- Independent audit exited 0 with `ok: true`, zero issues, 12,300 matching
  historical/export rows and 6,150 paired games, spanning 2021-10-19 through
  2026-04-12. Each of five seasons has 2,460 rows. All 40 reconstructed
  feature columns and 11 copied outcome/box-score columns matched on every
  row within 1e-9 with matching missingness. All opponent cardinality/identity
  and strictly earlier team-date checks passed.
- Data SHA-256: history
  `abbb5bc18a9eefb448013549e88e99e35b67444f40d63a6f6adb6f6dfeff90a1`;
  modeling export
  `f5045d6fd053764eedfe0adc301e0a5c23328dfe3a7b851e1b48867ec2b4ffc0`.
- Deliberately including the current score in a rolling mean is detected;
  tests also reject cumulative/opponent/difference contamination, invalid
  dates, non-strict team dates, bad joins, missing columns and row coverage.
  Tests verify in-memory and CSV inputs remain unchanged.
- Validation: all 15 unittest tests passed; unchanged syntax/notebook validator
  passed; audit was run independently. The worktree lacks `venv/bin/python`
  (initial invocation failed); used existing `../../venv/bin/python` 3.13.9
  for all successful checks. No venv changes or dependency installation.
- Notebook 03's current season split is chronological, but its exclusion of
  only 2025-26 could admit future seasons into training. Pipeline scaler fits
  on training rows. Multiple model comparisons/tuned variants expose 2025-26;
  it is not pristine. Reserve a new untouched future period prospectively.
  Notebook 02 uses aggregate season associations; notebook 06 trains on all
  available rows and reuses stale pregame state without an as-of-date filter.
- Limitations: supplied CSV consistency does not establish upstream provenance,
  historical availability, notebook/model execution history, downstream split
  correctness, or live prediction safety. Detailed evidence and cell references
  are in the audit document. No notebook execution, training, holdout scoring,
  dataset writes, production replacement, or task-status changes occurred.
