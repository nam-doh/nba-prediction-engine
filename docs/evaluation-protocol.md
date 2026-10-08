# Frozen chronological evaluation protocol — T003-v1

Frozen on 2026-10-08 before fitting this baseline. No candidate is fitted or
promoted by this task. The benchmark is a newly specified chronological
logistic baseline, not a reproduction of the notebook's exposed test scores.

## Partitions and sampling

Use calendar dates, with inclusive start and exclusive end boundaries:

| Partition | Date interval | Use |
| --- | --- | --- |
| Training | 2021-07-01 to 2024-07-01 | Fit preprocessing and classifier |
| Validation | 2024-07-01 to 2025-07-01 | Report baseline; later candidate selection |
| Exposed 2025-26 | 2025-07-01 to 2026-07-01 | Excluded from tuning, fitting and scoring |
| Reserved future 2026-27 | 2026-07-01 to 2027-07-01 | Untouched; no scoring here |

All other dates are excluded too. **2025-26 was repeatedly evaluated in existing
notebooks and is not a pristine holdout.** Reserve 2026-27 prospectively; do not
inspect its outcomes for feature/model selection. Before any eventual one-time
holdout evaluation, freeze the selected model, preprocessing, sampling policy
and acceptance decision in a separately authorized task. Do not use that result
to tune. Later iterations require a new untouched future period.

Partition whole dates, preserving both team rows and every game sharing a date.
Reject missing IDs, invalid dates, inconsistent game dates, non-paired games,
and targets without exactly one binary winner. Sort deterministically by date,
game ID and team ID. If either row has a missing selected feature, remove both
rows of that game within its partition; reject infinite features and empty
partitions. No random split, shuffle, or final-holdout tuning is allowed.
Evaluation is per team row; paired observations are dependent, so these metrics
do not imply twice as many independent games. No confidence claim is made.

## Frozen baseline and candidate gates

Use StandardScaler followed by LogisticRegression, C=1, lbfgs, max_iter=1000,
tol=0.0001, intercept enabled, no class weights, seed 42; installed sklearn
1.9.0 uses L2 via its default l1_ratio=0. Fit the pipeline only on training rows.
Predict validation win probabilities; accuracy thresholds probabilities at 0.5.
Report accuracy, ROC AUC, binary log loss and Brier score. Importing the script
never fits a model. CLI execution fits only an in-memory research baseline,
prints JSON to stdout, and writes no data, serialized models or production files.

The ordered feature list is frozen in `scripts/baseline.py`:
HOME_GAME, SEASON_WIN_PCT, WIN_STREAK, PTS_ROLL5, FG_PCT_ROLL5,
FG3_PCT_ROLL5, REB_ROLL5, AST_ROLL5, TOV_ROLL5, PLUS_MINUS_ROLL5,
WIN_PCT_ROLL5, REST_DAYS, OPP_PTS_ROLL5, OPP_WIN_PCT_ROLL5,
OPP_REST_DAYS, PTS_ROLL5_DIFF, PLUS_MINUS_ROLL5_DIFF, WIN_PCT_ROLL5_DIFF.
Only strictly earlier games may supply rolling/season/opponent values. T002's
read-only audit checks these exported historical statistics; HOME_GAME is
schedule metadata whose upstream historical availability is not independently
verified. Current-game box scores, outcome columns and completed-season
aggregates are never predictors.

Before fitting any future candidate, require all three gates on the identical
chronological validation sample and data version:

- Validation log loss strictly below **0.6299000714756492**.
- Validation Brier score at most **0.21985809688880792**.
- Validation ROC AUC at least **0.696234092099585** (baseline minus 0.005).

All values must be finite. Training accuracy is not a selection criterion;
validation accuracy is descriptive. `candidate_passes` evaluates these numerical
conditions but does not promote anything. A data/feature/sampling revision needs
a new recorded protocol and comparable baseline before candidate fitting;
never compare metrics computed on different retained games. Passing gates is
validation eligibility, not evidence of future performance or authorization to
replace production. Log candidate attempts to disclose repeated validation use.

## Reproduction and recorded result

From the repository root:

```sh
venv/bin/python scripts/baseline.py
venv/bin/python -m unittest discover -s tests -v
venv/bin/python scripts/validate.py
```

This worktree lacks `venv/bin/python`; actual runs used the existing
`../../venv/bin/python`, without environment changes or installation.
Versions: Python 3.13.9, pandas 3.0.5, numpy 2.5.1, sklearn 1.9.0.
`--data` selects a read-only input snapshot; alternate data is not automatically
a valid comparison to this frozen benchmark. SHA-256 is computed over the exact
CSV bytes parsed. Feature SHA-256 uses compact UTF-8 JSON of the ordered list.

- Data: `data/processed/team_game_modeling.csv`, SHA-256
  `f5045d6fd053764eedfe0adc301e0a5c23328dfe3a7b851e1b48867ec2b4ffc0`.
- Feature SHA-256:
  `24381691fe6584c9c3999fc70329fb2abfd03e4be0582a2ead0be99d5f66e3ed`.
- Training: 7,286 rows / 3,643 games, 2021-10-22 through 2024-04-14.
- Validation: 2,428 rows / 1,214 games, 2024-10-25 through 2025-04-13.
- Removed 126 incomplete rows / 63 games across eligible historical partitions;
  excluded all 2,460 supplied 2025-26 rows before feature processing.
- Accuracy: **0.6383855024711697**; ROC AUC: **0.701234092099585**;
  log loss: **0.6299000714756492**; Brier: **0.21985809688880792**.

Five focused regressions verify training-only scaler statistics, unchanged
inputs, exclusion of contaminated exposed/future features and outcomes, paired
missing-feature removal, same-date partitions, invalid-input rejection and gate
boundaries. All 20 repository tests and the unchanged syntax/notebook validator
pass. Tests fit only tiny synthetic fixtures; they never retrain production.

Limitations: these historical seasons were available during earlier notebook
exploration, so chronological validation is not an untouched experiment.
T002 verifies exported consistency, not acquisition-time provenance or revisions.
The future-period reservation assumes no prior inspection outside this task;
verify that assumption before eventual evaluation. Supplied data ends on
2026-04-12, so no actual 2026-27 holdout is available or scored. Baseline results
are environment-specific and do not establish future probability quality.
Notebooks and production consumers have not adopted this protocol here.
