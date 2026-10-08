# Reproducible evaluation report

`scripts/evaluation_report.py` is the read-only report entry point for the frozen
`T003-v1` protocol in [`evaluation-protocol.md`](evaluation-protocol.md). It reads
one CSV snapshot, fits the research baseline in memory, prints JSON, and never
writes datasets, models, or other artifacts.

## Reproduction

Run from the repository root with the existing environment:

```sh
venv/bin/python scripts/evaluation_report.py \
  --data data/processed/team_game_modeling.csv
```

The report is deterministic for unchanged input bytes and environment. JSON keys
are sorted and non-finite values are rejected. The input is hashed before parsing;
`data_sha256` identifies the exact CSV snapshot. `feature_sha256` hashes the
ordered frozen feature list from T003 using compact UTF-8 JSON.

## Report contract

Successful output contains:

- `protocol_id`, `seed`, `features`, `feature_sha256`, and library versions;
- `data_sha256` for the input bytes;
- frozen cutoff intervals and the reserved `[2026-07-01, 2027-07-01)` holdout;
- retained row/game counts and observed dates for `train` and `validation`;
- accuracy, ROC AUC, binary log loss, and Brier score.

Training is restricted to `[2021-07-01, 2024-07-01)` and validation to
`[2024-07-01, 2025-07-01)`. The exposed 2025-26 interval is excluded before
feature conversion and scoring; the reserved 2026-27 interval is not scored.
Whole games must remain paired, and a game cannot span partitions. Invalid dates,
identifiers, required feature columns, non-binary outcomes, infinite features,
and empty or single-class retained partitions fail closed with a nonzero exit.
Missing feature values remove both rows of that game, matching T003's frozen
sampling rule.

The historical validation interval was available during earlier notebook
exploration. It is reproducible, not a pristine holdout. The supplied data has no
2026-27 rows, so no future holdout result is reported.
