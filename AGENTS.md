# Project instructions

Use the existing `venv/bin/python` (Python 3.13.9); do not recreate it or install
requirements into it automatically. Installed pandas/sklearn differ from
requirements.txt. When an optional dependency is absent, validation may use a
separate environment outside the repository without modifying the protected venv.
The current pipeline lives in notebooks 02/03/06; collection and cleaning scripts
are under src. Run commands from the repository root.

Preserve all pre-existing edits. Do not edit user-dirty files unless the user
explicitly assigns those edits to the current task; inspect and preserve their
intent before changing them. Never edit credentials, venv, raw/processed datasets,
serialized models, exported HTML, or large artifacts. Git staging, commits, and
pushes are allowed only when the user explicitly authorizes them and only to the
named task branch. Never change branches, reset, merge, deploy, or schedule jobs.
No sub-agents.

Work on exactly the assigned TASKS.md entry and its explicit file allowlist.
Do not change the runner or validation commands. Change AGENTS.md, TASKS.md, or
task allowlists only when the user explicitly requests it. Add evidence and
limitations to PROGRESS.md. A task may be marked done only after its acceptance
criteria and independent validation pass; otherwise leave it pending and record
the blocker.

Validation: `venv/bin/python -m unittest discover -s tests -v` and
`venv/bin/python scripts/validate.py`. Add focused regression tests.

Prioritize leakage and temporal correctness before model optimization.
Pregame rolling/season/opponent statistics must use strictly earlier games;
keep both team rows and every same-date game in the same temporal partition.
Fit preprocessing only on training data. Never shuffle or tune on final holdout.
2025-26 was repeatedly evaluated in existing notebooks: disclose this exposure,
do not claim it is a pristine holdout. Reserve a new untouched future period.
For model changes, record a reproducible chronological baseline first (data
version, dates, features, seed, accuracy, ROC AUC, log loss, Brier score).
Define numerical validation acceptance criteria before fitting candidates;
require probability quality and out-of-time performance, not training accuracy.
Never retrain or replace production artifacts as a side effect of tests.
