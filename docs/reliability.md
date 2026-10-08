# Validation probability reliability — T006

This report measures the frozen T003 logistic baseline on the historical
validation interval only. It does not fit a calibrator, select or promote a
candidate, score the exposed 2025-26 period, or score the reserved 2026-27
holdout.

## Frozen evaluation

The CLI reuses the T003 protocol and its ordered 18-feature list:

- training: `[2021-07-01, 2024-07-01)`;
- validation: `[2024-07-01, 2025-07-01)`;
- exposed 2025-26: `[2025-07-01, 2026-07-01)`, excluded;
- reserved future 2026-27: `[2026-07-01, 2027-07-01)`, untouched.

`StandardScaler` and the logistic classifier are fit only on retained training
rows. The fitted baseline predicts validation probabilities; no probability
calibrator is fitted. Input validation is inherited from `scripts/baseline.py`:
invalid dates or identifiers, inconsistent game dates, incomplete two-team
games, invalid winners, infinite features, and empty or single-class partitions
fail closed. Missing selected features remove both rows of that game within its
partition.

Date partitioning happens before model fitting. Every row of a game stays in
one partition, and all games on a date share that partition. Validation metrics
are per team row and therefore paired: two rows from one game are dependent
observations, not two independent games.

## Report contents

Run from the repository root without an output path:

```sh
venv/bin/python scripts/reliability.py --data data/processed/team_game_modeling.csv
```

The command prints deterministic JSON and writes no files. The report includes:

- T003 protocol, feature, seed, cutoff, input SHA-256, and library metadata;
- retained train/validation row and game counts and dates;
- validation accuracy at probability 0.5, ROC AUC, binary log loss, and Brier
  score;
- validation sample count, counts for classes 0 and 1, and class prevalence;
- ten fixed calibration bins `[0.0, 0.1)`, ..., `[0.9, 1.0]`, each with its
  sample count, positive count, mean predicted probability, and observed
  prevalence.

The bin edges are constants, not quantiles computed from the observed
probabilities. Empty bins remain in the report with null means/prevalence, so
repeated runs cannot change bin boundaries because of sample composition.
Probabilities must be finite and in `[0, 1]`; missing or invalid probabilities
raise an error rather than being dropped.

## Regression coverage and limitations

`tests/test_reliability.py` verifies byte-stable rendering and fixed bins,
train-only/excluded-row isolation, same-date validation grouping, missing
probability rejection, complete game-pair enforcement, metrics, counts, and
prevalence. Tests use tiny in-memory fixtures and never write datasets, models,
or production artifacts.

2025-26 was repeatedly evaluated in existing notebooks, so the T003 validation
interval is not a pristine experiment. The report measures probability
reliability on that fixed historical validation sample; it does not establish
future calibration or confidence intervals. The reserved 2026-27 period must
remain untouched until a separately authorized one-time holdout evaluation.
