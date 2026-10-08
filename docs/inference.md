# Historical inference API

`src/modeling/inference.py` exposes `InferenceEngine` and the one-shot
`predict_matchup` entry point. Both load the read-only
`models/logistic_regression_production.pkl` pipeline and the historical
`data/processed/team_game_modeling.csv` feature export. They never fit,
calibrate, replace, or write a model, dataset, or prediction export.

## As-of behavior

`InferenceEngine.predict_matchup` requires two different known teams, an
explicit hypothetical date, and integer rest inputs from 0 through 14. Team
state selection filters every history row with `GAME_DATE < game_date` before
selecting the latest state. Same-date and future rows cannot contribute to
state, rest inputs, or the derived next team-game number. Missing or
non-finite state features fail closed with an `InferenceError`.

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

**T007 is still pending.** The current implementation selects stored
pregame rows; it does not use T007's not-yet-implemented feature builder or
recompute rolling and cumulative statistics from completed game outcomes.
Stored pregame values exclude the selected row's own game. Consequently,
`home_state_date` / `away_state_date` are row dates, not evidence that the
model incorporated the results played on those dates. The April 12 row is
not a post-April-12 snapshot.

For a date after the source cutoff, selecting a later date does not update
statistics. `_next_team_game_number` counts earlier rows in the selected
state's season plus one: with this export it remains 83, including for dates
in a subsequent season. No season rollover, cold-start blending, intervening
schedule simulation, or automatic rest calculation is implemented. Rest is
explicit user input, not verified schedule history. New-season forecast
quality is not established. T008's requirement to reuse T007 is unmet;
the current implementation must not be described as completing that dependency.

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

An isolated read-only smoke exercised all 870 orientations on 2026-04-13,
using two rest days per team; outputs were finite, bounded, complementary,
and used April 12 state rows. This establishes execution coverage, not
forecast accuracy or calibration. No production fitting or artifact writes
occurred. Source/model hashes before and after that run were identical:

- Feature export SHA-256:
  `f5045d6fd053764eedfe0adc301e0a5c23328dfe3a7b851e1b48867ec2b4ffc0`
- Model SHA-256:
  `292fc17174f370e9785ab29fe380d2591ea6f3be3bc31a2ff4eaeb25e1d39bc6`
