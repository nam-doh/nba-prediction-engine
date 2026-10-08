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

## T003 — protocol and acceptance evidence — 2026-10-08
- Added frozen T003-v1 protocol, read-only baseline CLI and five focused
  regression tests. Edited only docs/evaluation-protocol.md,
  scripts/baseline.py, tests/test_baseline.py and this log. TASKS.md is unchanged;
  task status is left for independent runner validation. No Git mutations.
- Defined gates before fitting: strictly lower validation log loss, Brier no
  worse, and ROC AUC decrease at most 0.005. No candidates or promotions.
- Training interval [2021-07-01, 2024-07-01); validation
  [2024-07-01, 2025-07-01). Scaler fitted exclusively on training. Both rows
  and all same-date games share a partition; missing features remove whole
  game pairs. Frozen ordered 18-feature list and seed 42 are in the protocol.
- Actual retained training: 7,286 rows / 3,643 games, 2021-10-22–2024-04-14;
  validation: 2,428 rows / 1,214 games, 2024-10-25–2025-04-13.
  Removed 126 incomplete historical rows (63 games); excluded 2,460 exposed
  2025-26 rows. Accuracy 0.6383855024711697, ROC AUC 0.701234092099585,
  log loss 0.6299000714756492, Brier 0.21985809688880792.
- Data SHA-256:
  `f5045d6fd053764eedfe0adc301e0a5c23328dfe3a7b851e1b48867ec2b4ffc0`;
  ordered feature SHA-256:
  `24381691fe6584c9c3999fc70329fb2abfd03e4be0582a2ead0be99d5f66e3ed`.
  CLI emits these hashes, cutoffs, seed, model parameters and library versions.
- Successful independent baseline command: `../../venv/bin/python scripts/baseline.py`.
  Both required validations passed using that existing interpreter:
  `../../venv/bin/python -m unittest discover -s tests -v` (20 tests) and
  `../../venv/bin/python scripts/validate.py`. The requested local
  `venv/bin/python` remains absent; no environment changes or installs.
  Python 3.13.9, pandas 3.0.5, numpy 2.5.1, sklearn 1.9.0.
- Regression evidence: scaler means equal training-only means despite shifted
  validation values; corrupting exposed/future features and outcomes leaves
  the report unchanged; missing one team's feature removes both game rows;
  invalid dates/IDs/targets/features and empty partitions fail closed;
  numerical gate equality/degradation/nonfinite cases are checked.
- Explicitly disclosed repeated 2025-26 evaluation and excluded it from tuning,
  fitting and scoring. Reserved [2026-07-01, 2027-07-01) / season 2026-27
  untouched; supplied data has no such rows and no future holdout was scored.
- Limitations: historical validation itself follows prior notebook exploration;
  provenance and external future-outcome exposure are unverified. Metrics are
  dependent paired-row summaries, not independent-game confidence estimates.
  No notebook adoption, data/artifact writes or production model replacement.

## T004 — OMP runner integration evidence — 2026-10-08
- Added focused regression coverage in `tests/test_runner.py`. The OMP
  command must use print mode (`-p`), JSON output, noninteractive controls,
  and the explicit `openai-codex` provider / `gpt-5.6-luna` model. A reported
  provider mismatch raises `RuntimeError`; advisor execution is absent.
- Smoke result: local command-construction and provider-log verification passed:
  `../../venv/bin/python -m unittest tests.test_runner -v` — 7 tests passed.
  No OMP worker or advisor call was made, per the task restriction.
- Model/provider recorded for the smoke configuration:
  `gpt-5.6-luna` / `openai-codex`. Reported token usage: **N/A** because no
  OMP process was invoked; no live usage value is claimed.
- Required validation passed:
  `../../venv/bin/python -m unittest discover -s tests -v` — 22 tests passed;
  `../../venv/bin/python scripts/validate.py` — syntax and notebook structure
  valid, with no training/holdout execution. `TASKS.md` was unchanged; no Git
  mutations, dataset/model/notebook changes, or environment installs occurred.
- Limitation: this verifies runner wiring and fail-closed provider checking, not
  live OMP authentication, network execution, or token accounting.
