# Historical pregame leakage audit — T002

Audited on 2026-10-08 without executing notebooks, fitting models, scoring a
holdout, or modifying data. The supplied CSV contents pass the implemented
historical feature checks. This establishes consistency with the cleaned game
history, not independent verification of that history's provenance.

## Reproduce and acceptance criteria

Run from the repository root:

```sh
venv/bin/python scripts/audit_leakage.py
venv/bin/python -m unittest discover -s tests -v
venv/bin/python scripts/validate.py
```

This automation worktree has no `venv` directory. These commands were run using
`../../venv/bin/python`, the existing repository environment (Python 3.13.9).
No environment was created or dependencies installed. The unchanged validator
checks syntax and notebook structure; the audit must also be run independently.

Acceptance requires audit exit code 0, `ok: true`, no structural or feature
issues, matching missingness, and numeric agreement within absolute/relative
1e-9. Any failure returns exit code 1. Inputs can be selected with `--history`
and `--modeling`; JSON goes to stdout with input SHA-256 hashes, check counts,
issue counts, and at most 20 diagnostic samples. No output files are created.

The reference is `team_game_logs_clean.csv`, independently of the exported
feature values in `team_game_modeling.csv`. Per season/team, dates are sorted
and must be strictly increasing. Duplicate team dates fail closed rather than
allowing a row shift to include another game on the same date. Each game must
have exactly two distinct teams with one shared date in both inputs. Row keys
must match across inputs; dates and copied outcomes/box scores are compared.
Unsorted file order is permitted and is not itself evidence of leakage.

Reconstruction resets at each season, uses only earlier games for all ten
box-score rolling means and rolling win percentage (last five games,
minimum one available value), previous win/points, prior cumulative wins/games,
season win percentage, game number, rest, and pregame win streak. Opening-game
means and percentages must be missing. Rest reproduces notebook 03's elapsed
days between games, rather than subtracting one for days off. Opponent IDs,
all 12 joined opponent features, and all nine difference features are checked
against the other team's independently reconstructed pregame values.

## Actual data evidence

Both files contain 12,300 rows, with exactly two team rows for each of 6,150
games. No duplicates, missing counterparts, inconsistent game dates, same-day
team histories, opponent identity errors, or numerical mismatches were found.
All 40 reconstructed feature columns were checked on every row, including
missing opening-game values. Eleven copied outcome/box-score columns were
also compared on every row; 12,300 opponent cardinality checks passed.

| Season | Rows | First game | Last game |
| --- | ---: | --- | --- |
| 2021-22 | 2,460 | 2021-10-19 | 2022-04-10 |
| 2022-23 | 2,460 | 2022-10-18 | 2023-04-09 |
| 2023-24 | 2,460 | 2023-10-24 | 2024-04-14 |
| 2024-25 | 2,460 | 2024-10-22 | 2025-04-13 |
| 2025-26 | 2,460 | 2025-10-21 | 2026-04-12 |

Input SHA-256:

- Clean history: `abbb5bc18a9eefb448013549e88e99e35b67444f40d63a6f6adb6f6dfeff90a1`
- Modeling export: `f5045d6fd053764eedfe0adc301e0a5c23328dfe3a7b851e1b48867ec2b4ffc0`

Seven focused tests pass, alongside eight existing tests. They cover unsorted
paired rows, season reset, five-game window boundaries, opening missingness,
read-only execution, CLI exit status, malformed schema/dates/targets, duplicate
or missing opponents, wrong opponent IDs, date divergence, and deliberately
contaminated rolling/cumulative/opponent/difference features. The contamination
regression replaces the second game's prior-only points mean (1) with a mean
including its current score (2.5) and detects precisely that feature mismatch.

## Notebook findings and limitations

Notebook 02 analyzes aggregate season statistics against season win percentage.
Those correlations describe completed-season associations; those aggregates
would leak future outcomes if used as pregame inputs. Notebook 03 instead loads
game logs and explicitly shifts rolling statistics and subtracts current wins
from cumulative wins (cells 7–10, zero-based). Its opponent merge (cell 12)
merges on season/game then removes self rows; it lacks an enforced merge
cardinality assertion. The current export has the required two-team cardinality.

Notebook 03's split in cells 20 and 26 places season 2025-26 in `test_df` and
all other seasons in training. The current dates are chronologically separated,
and the season split keeps game pairs and same-date games together before
feature filtering. The season inequality is not an explicit cutoff guard: newly
added later seasons would enter training. Dropping missing features per row can
also remove a single member of a game pair; partition membership and paired
sample retention are separate concerns. No notebook adoption of T001 was made.

The logistic pipeline fits its scaler on `X_train` through `Pipeline.fit`
(cells 33–35). Several classifiers predict/score the same 2025-26 test rows,
and the comparison table includes tuned variants (cells 43–108). **2025-26 is
exposed, not a pristine holdout.** Model selection must use a chronological
training/validation protocol and reserve a new untouched future period, such
as 2026-27, prospectively before scoring or tuning. This task neither defines
the T003 protocol nor evaluates that future period.

Notebook 06 fits a scaler/classifier pipeline on all available complete rows,
including 2025-26 (cells 7–10), and exports a production model later. Its latest
team state takes the last row's *pregame* features (cells 12–13), which omit
that row's own result. This is stale state for a later game. State selection is
not constrained to be earlier than a requested prediction date, so historical
back-predictions could consume future information. Schedule-only rest/game
counts also need a separate live-state audit. No notebook or artifact was run
or changed.

The audit does not verify upstream NBA acquisition timestamps, original raw
source correctness, whether data was revised later, or real-time availability
of every statistic. It compares supplied files, not saved notebook execution
history or serialized model provenance. Missing box-score values follow
available-value rolling means; missing targets and nonfinite numbers fail.
It does not certify unlisted features, home/away metadata, actual downstream
partition use, live inference, or probability quality. No model changed, so
baseline fitting and candidate promotion gates are outside T002.
