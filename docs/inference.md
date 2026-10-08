# Historical inference API

`src/modeling/inference.py` exposes `InferenceEngine` and the one-shot
`predict_matchup` entry point. Both load the read-only
`models/logistic_regression_production.pkl` pipeline and the historical
`data/processed/team_game_modeling.csv` feature export. They never fit,
calibrate, replace, or write a model, dataset, or prediction export.

## As-of behavior

`InferenceEngine.predict_matchup` requires two different known teams and an
explicit hypothetical date. It reuses T007's completed-game builder, excluding
all same-date/future rows before validating and reconstructing team states.
Rest defaults to elapsed calendar days since each team's prior same-season game;
optional integer overrides (0–14) represent explicit hypothetical scenarios.
Missing/nonfinite final model features fail closed with `InferenceError`.

The feature frame is checked against the persisted pipeline's exact ordered
36-feature contract before `predict_proba` runs. The result contains home and
away probabilities, home/away orientation, each state date, the last source
date used, the static data cutoff, model artifact, and assumptions metadata.

## Data limitations

The static source contains 12,300 team rows / 6,150 games dated 2021-10-19
through **2026-04-12**, covering 30 teams. All teams' latest rows are dated
2026-04-12. The UI supports any pair of distinct names from this export
(435 unordered pairs, 870 choices of home/away orientation), dates starting
2026-04-13, and integer rest inputs from 0 through 14 for each team. Names
must match the source, including `LA Clippers`; no aliases are resolved.
The matchup need not be on a real schedule.

T007's canonical builder recomputes rolling and cumulative statistics from raw
completed-game columns, ignoring exported pregame values. State dates now name
the last completed games actually incorporated. The July season boundary resets
history; without same-season history a subsequent-season request fails rather
than recycling the previous season's game 83. No live schedule is fetched.
Rolling means omit missing source observations, matching the audited training
convention; an entirely missing rolling window remains missing and fails inference.
The static source includes one missing FT_PCT, not a fabricated zero.

The API also accepts earlier dates when finite prior state exists, but its
production model was not trained afresh as of each requested date. Those
calls are not leakage-free historical backtests or out-of-time evaluations.
The UI deliberately only offers dates after the static cutoff.

No network or live schedule lookup occurs. Injuries, lineups, trades, and
player availability are absent. Probabilities are historical estimates,
not guarantees. The 2025-26 season was repeatedly examined in prior notebook
work and is not pristine; [2026-07-01, 2027-07-01) remains the reserved
future holdout, unscored by this UI work.

## Runtime and reproducibility

Follow the [isolated UI setup in the README](../README.md#running-locally).
Use the same interpreter for dependency installation, the full test suite,
`scripts/validate.py`, and `python -m streamlit run`. The earlier system
Streamlit smoke used scikit-learn 1.8.0 against a 1.9.0 pickle and is not
the supported runtime. The selected runtime pins scikit-learn 1.9.0 and
Streamlit 1.65.0 (which supports pandas 3), with all installed UI dependency
versions constrained by `requirements.txt` on the tested macOS ARM64 platform.

The earlier 870-orientation smoke tested the superseded stored-row adapter.
After the canonical cutover, direct real-model Boston/OKC inference on 2026-04-13
returned 0.6135600271 / 0.3864399729 with one elapsed rest day and April 12 state.
This is execution coverage, not forecast-quality validation. No fitting or
artifact writes occurred. Previously recorded immutable source hashes:

- Feature export SHA-256:
  `f5045d6fd053764eedfe0adc301e0a5c23328dfe3a7b851e1b48867ec2b4ffc0`
- Model SHA-256:
  `292fc17174f370e9785ab29fe380d2591ea6f3be3bc31a2ff4eaeb25e1d39bc6`
