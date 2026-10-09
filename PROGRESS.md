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
- Direct read-only OMP smoke returned `OMP_SMOKE_OK` with provider
  `openai-codex` and model `gpt-5.6-luna`; reported usage was 2,275 total
  tokens (2,267 input, 8 output). No tools, workers, or advisor were enabled.
- Bounded T004 execution used the same provider/model and reported 7,028 total
  tokens (6,893 input, 135 output; 49 reasoning tokens). The runner's log is
  `.automation/logs/20261008-001738-27530/T004-attempt-0.jsonl`.
- Required validation passed:
  `../../venv/bin/python -m unittest discover -s tests -v` — 22 tests passed;
  `../../venv/bin/python scripts/validate.py` — syntax and notebook structure
  valid, with no training/holdout execution. `TASKS.md` was unchanged; no Git
  mutations, dataset/model/notebook changes, or environment installs occurred.
- Limitation: only the selected `openai-codex`/`gpt-5.6-luna` path was exercised;
  alternate provider/model choices and timeout/retry recovery were not live-tested.

## T005 — reproducible evaluation reports — 2026-10-08
- Added read-only `scripts/evaluation_report.py`, four focused regression tests,
  and `docs/evaluation-report.md`. Only the T005 allowlist plus this progress
  log was edited; `TASKS.md` remains unchanged. No Git mutations, dataset/model/
  notebook writes, artifact replacement, or package installation occurred.
- The CLI parses one input snapshot, hashes the exact CSV bytes, evaluates only
  the frozen T003-v1 training interval [2021-07-01, 2024-07-01) and validation
  interval [2024-07-01, 2025-07-01), and emits sorted-key JSON containing the
  ordered feature list/hash, seed, Python/pandas/numpy/sklearn versions,
  cutoff intervals, retained row/game counts and observed dates, and accuracy,
  ROC AUC, log loss, and Brier metrics. It fits only the in-memory baseline;
  no report/model/data files are written.
- Repeated CLI smoke runs on one unchanged synthetic CSV returned
  `CLI_SMOKE_OK` with byte-identical 1,574-byte stdout. An invalid-date CLI
  smoke returned exit code 1 with no stdout (`CLI_INVALID_OK`). Focused
  `tests.test_evaluation_report` passed all 4 tests, covering byte identity,
  exposed/future-row exclusion, invalid dates/IDs/missing feature columns,
  mixed partitions, and input immutability.
- Required validation passed with the existing `../../venv/bin/python`:
  `../../venv/bin/python -m unittest discover -s tests -v` — 26 tests passed;
  `../../venv/bin/python scripts/validate.py` — syntax and notebook structure
  valid, with no training/holdout execution.
- Limitations: this task did not execute the default production dataset or
  inspect 2025-26/2026-27 outcomes. Historical validation remains exposed to
  prior notebook exploration and is not a pristine holdout; the reserved
  2026-27 period has no scored result. The report reuses T003's in-memory
  baseline and paired team-row metrics, so scores are not independent-game
  confidence estimates.


## T006 — validation probability reliability — 2026-10-08
- Added read-only `scripts/reliability.py`, six focused regression tests, and
  `docs/reliability.md`. Only the T006 allowlist plus this progress log was
  edited; `TASKS.md` remains unchanged. No Git mutations, package installation,
  dataset/model/notebook writes, calibrator fitting, candidate promotion,
  holdout scoring, or production replacement occurred.
- The report reuses the frozen T003 baseline, fitting `StandardScaler` and the
  logistic classifier only on retained training rows and scoring only
  validation rows in `[2024-07-01, 2025-07-01)`. It emits accuracy, ROC AUC,
  log loss, Brier score, validation sample/class counts and prevalence, plus
  ten deterministic fixed-width calibration bins `[0.0, 0.1)` through
  `[0.9, 1.0]`. Empty bins remain explicit; missing, non-finite, or out-of-range
  probabilities fail closed.
- Focused `tests.test_reliability` passed — 6 tests. Coverage includes
  byte-stable output, fixed bin edges, missing probabilities, excluded
  2025-26/future-row contamination, same-date grouping, incomplete pairs,
  metrics, sample counts, and prevalence.
- CLI smoke on a tiny in-memory synthetic CSV returned
  `RELIABILITY_CLI_SMOKE_OK` and printed JSON. Full validation passed with the
  existing `../../venv/bin/python`: `python -m unittest discover -s tests -v`
  — 32 tests passed; `python scripts/validate.py` — syntax and notebook
  structure valid, with no training/holdout execution.
- No production dataset or model binary was inspected or scored. Historical
  T003 validation was repeatedly exposed in prior notebooks and is not a
  pristine calibration experiment; the report does not establish future
  probability quality or confidence intervals. The paired team-row metrics are
  dependent observations, not independent-game estimates. The reserved
  2026-27 period remains unscored and must stay untouched until separately
  authorized.

## UI backlog planning — 2026-10-08
- Added ordered pending T008–T010 entries to `TASKS.md` only for a reusable
  as-of inference API, Streamlit UI, and interface smoke/documentation work.
  Existing T001–T007 entries were preserved; no interface implementation,
  notebook, dataset, model, or dependency changes were made.
- Inspection found the persisted artifact is a scikit-learn `Pipeline` with
  `scaler` and `classifier` steps and an ordered 36-feature contract. The
  live notebook currently trains/reuses that pipeline, derives latest state
  from `team_game_modeling.csv`, and documents static statistics and absent
  injury/lineup inputs. The modeling data spans 2021-10-19 through 2026-04-12
  and contains 30 teams; `dashboards/` has no implementation. Streamlit is
  not installed in the existing environment, so the future AppTest smoke
  requires the dependency declared by T009 before T010 validation.
- Validation passed without training or artifact writes:
  `../../venv/bin/python -m unittest discover -s tests -v` — 32 tests;
  `../../venv/bin/python scripts/validate.py` — syntax and notebook
  structure valid; task parser — `TASKS_FORMAT_OK` for T001–T010.
- Limitation: this backlog does not execute the future inference/UI tasks,
  install dependencies, or prove current-data availability. No Git mutation,
  commit, branch change, or push was performed.

## T006 review revalidation — 2026-10-08
- Rechecked the reliability implementation after the automation stop with the
  existing `../../venv/bin/python`; the worktree-local `venv/bin/python` is
  absent.
- `../../venv/bin/python -m unittest tests.test_reliability -v`: 6 tests
  passed. Full discovery: 32 tests passed. `../../venv/bin/python
  scripts/validate.py`: syntax and notebook structure valid.
- The latest automation log directories
  `.automation/logs/20261008-003953-28930/`,
  `.automation/logs/20261008-003921-28918/`, and
  `.automation/logs/20261008-003916-28911/` contain no attempt, check, or push
  output. The preceding T006 attempt explicitly prohibited Git mutations and
  ended after writing the four T006 files; the only nearby push log records the
  earlier T005 commit. This explains why T006 remains uncommitted.
- T006 meets its stated acceptance criteria from the implementation and
  passing regressions. T006 and the interface backlog entries remain pending in
  `TASKS.md` because task status is runner-managed; no interface work was
  implemented.
## T008–T010 — historical inference UI implementation — 2026-10-08
- Added `src/modeling/inference.py` with a read-only `InferenceEngine` and
  `predict_matchup` entry point. It loads the existing production
  `Pipeline`, verifies the ordered 36-feature contract, filters team state
  strictly to `GAME_DATE < game_date`, validates rest/date/team inputs, and
  returns oriented probabilities plus source dates, cutoff, model, and
  assumptions metadata. It never fits or writes artifacts.
- Added six inference regressions covering a known real-model matchup,
  probability invariants and metadata, same-date/future-row exclusion,
  invalid inputs, missing files, and a no-fit/no-mutation guard. Focused
  command passed: `../../venv/bin/python -m unittest tests.test_inference -v`
  — 6 tests passed. Direct smoke returned finite probabilities
  (Boston Celtics 53.24%, Oklahoma City Thunder 46.76%) using states through
  2026-04-12.
- Added `dashboards/app.py`, an offline Streamlit matchup interface with
  distinct team selectors, explicit home-team selection, bounded rest inputs,
  a validated date after the static cutoff, probability bars, model/source
  metadata, loading/error states, and historical-data/injury-lineup
  disclosures. Added `streamlit==1.50.0` to `requirements.txt` and documented
  setup/launch/limitations in `README.md`. No app prediction uses
  `latest_predictions.csv` or writes any artifact.
- Added `tests/test_streamlit_app.py` with a real `AppTest` success and
  duplicate-team failure path. The existing environment does not contain
  Streamlit (`pip show streamlit` returned package not found), so AppTest,
  local launch, and browser visual inspection are blocked without installing
  the declared dependency. No package installation was performed under the
  repository instructions. Python compilation passed for all changed modules.
- No notebook, dataset, model, holdout, or user-dirty file was changed.
  `src/modeling/pregame_features.py` from pending T007 does not exist; this
  API therefore consumes the existing precomputed pregame feature export and
  applies the required strict as-of filter rather than duplicating rolling
  feature construction. No Git staging, commit, branch operation, or push
  was performed because repository instructions prohibit those operations.

## UI verification follow-up — 2026-10-08
- The first local launch surfaced a real import-path failure when Streamlit
  executed `dashboards/app.py` directly (`ModuleNotFoundError: src`). Added a
  repository-root path bootstrap before importing the inference API.
- Relaunched with `streamlit run dashboards/app.py --server.headless true
  --server.port 8501`. Browser inspection rendered the basketball-themed hero,
  sidebar selectors, rest controls, hypothetical date, probability bars, model
  metadata, and missing-injury/lineup warning. Clicking Predict rendered both
  probabilities and the as-of metadata; the service and browser tab were then
  stopped.
- Real `AppTest` smoke tests passed with the installed system Streamlit:
  `python -m unittest tests.test_streamlit_app -v` — 2 tests passed. The
  required existing `../../venv/bin/python` still lacks Streamlit, so full
  unittest discovery under that interpreter reports one import error for
  `test_streamlit_app`; this is an environment dependency blocker, not a
  silent test skip. `../../venv/bin/python scripts/validate.py` passed.

## UI reproducibility and automation blockers — 2026-10-08
- Diagnosed the two distinct runtime failures: the original venv has no
  Streamlit, whereas system Python has Streamlit 1.51.0 and sklearn 1.8.0.
  System sklearn mismatches the persisted pipeline's 1.9.0 metadata.
  Streamlit 1.51.0's declared pandas<3 constraint also conflicts with the
  project's pandas 3 pins; the earlier system-AppTest pass did not establish
  a compatible supported environment.
- Per the request for isolation, bootstrapped a separate Python 3.13.9
  environment at `/tmp/nba-ui-repro.5gYnii` using `../../venv/bin/python`.
  The existing venv and system Python were not modified. Only the UI/test
  dependency closure was installed there, not the notebook requirements set.
  `requirements.txt` now pins Streamlit 1.65.0, sklearn 1.9.0, pandas 3.0.5,
  NumPy 2.5.1, SciPy 1.17.1, joblib 1.5.3, and the additional UI dependencies.
  All 39 installed runtime distributions matched constraints; `pip check`
  returned `No broken requirements found.` These are version pins, not an
  artifact-hash lock; verification was macOS ARM64 only.
- Exact selected-environment verification:
  `/tmp/nba-ui-repro.5gYnii/bin/python -m unittest discover -s tests -v`
  passed all **52 tests**, including both Streamlit AppTests, with zero import
  errors or skips. `/tmp/nba-ui-repro.5gYnii/bin/python scripts/validate.py`
  passed. Joblib/NumPy deprecation and pre-existing invalid-date fixture
  warnings remain visible; no version-mismatch warning occurred.
- Independent API smoke exercised all 870 oriented matchups across 30 teams
  on 2026-04-13 with two rest days per team. Every result was finite, bounded,
  complementary, and used 2026-04-12 state rows. Source and model hashes were
  unchanged. This is execution coverage, not forecast-quality validation.
- Launched the isolated interpreter's Streamlit on loopback port 8513 with
  telemetry disabled and `--theme.base light`; a browser Predict interaction
  displayed probabilities and metadata. The explicit theme avoids unreadable
  light-background text under inherited dark settings. A smoke attempt on
  port 8501 encountered mixed-version client/server errors while an unrelated
  wildcard listener was already present. That pre-existing process was not
  stopped; only services started for these checks and their tabs were closed.
- README now documents guarded environment creation outside the repository,
  constrained UI installation, full validation, and the exact local launch.
  `docs/inference.md` documents the 2026-04-12 precomputed feature cutoff,
  supported teams/date/rest inputs, stale pregame-row semantics, and lack of
  season reset (current next-game count stays 83). T007 remains pending and
  unchanged. T008's T007 dependency is explicitly unmet; historical as-of
  filtering is not described as leakage-free backtesting of the fitted model.
- Automation is **not ready**: `scripts/improve.py:23,124-125` hardcodes the
  original checkout's venv, regardless of PATH, VIRTUAL_ENV, or the
  interpreter launching the runner. That environment still lacks Streamlit.
  No runner or validation-command change, worker launch, or scheduling was
  performed. Isolated validation must not be mistaken for passing runner
  validation.
- Governing repository instructions still prohibit editing AGENTS.md, changing
  the runner/validation commands, and Git staging/commits/pushes. User
  authorization cannot supersede those supplied rules in this session.
  Publication to automation/nba-improvements therefore remains blocked.
  Only requirements, README, inference documentation, and this appended log
  were changed in this follow-up. Prior progress and task-manifest edits were
  preserved; no task status, data, notebook, production model, or holdout was
  changed. No merge or public deployment occurred.

## T008–T010 — authorized UI validation and publication — 2026-10-08
- The user explicitly authorized the narrow project-rule and Git exceptions.
  `AGENTS.md` now permits a separate environment for optional dependencies and
  user-authorized edits/publication to a named task branch while retaining the
  protections for credentials, environments, data, models, notebooks, branch
  changes, resets, merges, scheduling, deployment, and sub-agents.
- Revalidated the complete worktree with the existing isolated Python 3.13.9
  environment at `/tmp/nba-ui-repro.5gYnii`: `pip check` reported no broken
  requirements; `python -m unittest discover -s tests -v` passed all 52 tests;
  and `python scripts/validate.py` passed syntax and notebook validation. The
  protected repository venv was not modified.
- T009 and T010 meet their acceptance criteria and are marked done. T008 stays
  pending because its explicit T007 dependency remains unmet: the historical
  adapter filters precomputed rows by as-of date but cannot yet reuse the
  absent canonical T007 pregame builder. This limitation is visible in the UI
  and documented in `docs/inference.md` and the README.
- The automation runner still hardcodes the protected venv, which lacks
  Streamlit. This does not block the separately validated local UI, but runner
  UI validation requires a future authorized configuration change. No model,
  dataset, notebook, or holdout was changed or scored.

## T011–T014 — player source, snapshots, rosters, and statistics — 2026-10-08
- Added runner-format T011–T020 entries with explicit file allowlists and
  dependencies. T011–T014 are complete after focused and full independent
  validation; T015–T020 remain pending. The backlog orders official
  availability and news before contribution modeling, chronological candidate
  evaluation, inference integration, and UI integration.
- `docs/player-data-sources.md` records primary documentation, current cost,
  authentication, quotas, permitted-use constraints, history, freshness, and
  observed access for NBA.com, official NBA injury PDFs, BALLDONTLIE,
  TheSportsDB, GNews, and unentitled commercial alternatives. NBA.com numeric
  IDs were selected. NBA.com roster/stats endpoints require no key; the future
  optional GNews adapter requires `GNEWS_API_KEY` and its free plan is limited
  to development/testing, 100 requests/day, a 12-hour delay, and 30 days of
  history. No subscription or payment-backed trial was used.
- Added a dependency-free immutable JSON snapshot store with UTC retrieval and
  optional source-as-of timestamps, request/source provenance, raw and
  normalized payloads, SHA-256 verification, deterministic JSON, atomic
  no-overwrite publication, credential query redaction, exact-request latest
  lookup, corruption/path validation, and `data/snapshots/` Git exclusion.
  Production defaults write ignored runtime state; tests and live probes wrote
  only to temporary directories.
- Added injectable `commonteamroster` and league-wide `playergamelogs` adapters
  plus refresh CLIs. Rosters preserve NBA player/team IDs, permit duplicate
  names and cross-snapshot trade memberships, cache for one hour, default to a
  three-second inter-request delay, retain successful team snapshots on partial
  failure, and exit nonzero when any requested team fails. Player logs preserve
  textual game IDs, ISO dates, historical team IDs, minutes/core box scores,
  and six-hour exact-request caching. Both reject malformed/duplicate required
  identities and never fabricate fallback data.
- **Live verified:** one official NBA.com Boston `2026-27` roster request
  returned 21 normalized rows at `2026-10-08T17:13:25.292463Z`; one official
  NBA.com `2025-26` regular-season player-log request returned 26,651 rows at
  `2026-10-08T17:13:51.108356Z`. Repeating each refresh without `--force`
  returned the same snapshot as a cache hit without network. A TheSportsDB
  free-key probe returned only 10 NBA teams, confirming that it is not a
  complete primary roster source. Live payloads remain under
  `/tmp/nba-player-live-probe` and were not staged.
- Fixture validation with the protected `../../venv/bin/python` passed 14
  focused tests covering snapshot immutability/corruption/redaction, duplicate
  names and trades, partial failures, cache behavior, CLI exit/reporting,
  temporal fields, optional statistics, invalid data, and no fallback.
  Full validation in the separate compatible Python 3.13 UI environment passed
  all 66 tests with no skips; `scripts/validate.py` passed. No dependency was
  installed into the protected venv.
- Limitations: NBA stats endpoints have no published API SLA or rate limit and
  NBA terms restrict public/commercial reuse of Basketball Content; raw
  snapshots must not be committed or redistributed. A roster snapshot proves
  membership only at retrieval time and cannot be applied retrospectively.
  Player logs contain no historical pregame injury state. An official injury
  PDF was live-accessible, but no complete public historical report index was
  verified. T015 must audit and collect timestamped reports going forward;
  unavailable history stays missing. The 2025-26 probe was ingestion-only and
  did not fit, tune, predict, or score the exposed period or reserved holdout.

## T007 — canonical construction — 2026-10-08
- Implemented raw completed-game rolling, season, elapsed-day rest and one-to-one
  opponent features. Same-date games are excluded together; new-season missing
  history stays NaN. Duplicate/missing opponents and unsorted histories fail.
- Four focused regressions passed; full isolated discovery passed 70 tests;
  protected-interpreter `scripts/validate.py` passed. Independent in-memory
  smoke printed correct paired 11/12 point rolling values, two-day rest and
  missing first-game/new-season features. No data/model/holdout writes.
- Calendar-date reconstruction cannot establish upstream publication timestamps.

## T008 — canonical inference cutover — 2026-10-08
- Reused T007 state/opponent construction; removed duplicated/stale precomputed
  assembly. Verified exact scaler/classifier feature/class contract. Automatic
  elapsed-day rest is the default; explicit overrides remain labeled scenarios.
  Subsequent seasons without history fail closed.
- Source inspection found one missing FT_PCT. Rolling means preserve the audited
  skip-missing convention; wholly missing feature windows fail inference.
- Eight inference regressions and full isolated discovery passed (72 tests).
  Protected-interpreter syntax/notebook validation passed. Direct real-model
  Boston/OKC smoke on 2026-04-13 returned 0.6135600271453063 and its complement,
  April 12 states and one elapsed rest day. No training or holdout scoring.
- T007/T008 marked done only after independent validation. T006 implementation
  and its six tests were reused unchanged; no duplicate reliability module.

## T015 — official PDF availability — 2026-10-08
- Added conservative robots-aware official PDF ingestion, immutable raw PDF plus
  normalized provenance, unique roster/name resolution and explicit unresolved/
  ambiguous identities. Missing reports/submissions remain unknown; no health
  inference from omission. Fifteen-minute caching and timestamped revisions.
- Live HTTP 200 probe: April 4 00:45 ET PDF, 68,500 bytes, 51 parsed rows,
  including 23 NOT YET SUBMITTED teams. Three-page continuation/wrapped reasons
  inspected. Snapshot `/tmp/nba-official-live-probe/.../20261008T174452782859Z_6f95cf5e9233e32c.json`;
  retrieval 2026-10-08, source-as-of 2026-04-04T04:45Z; cache hit observed.
- Three focused tests and 75-test isolated discovery passed; protected syntax/
  notebook validator and isolated `pip check` passed. Installed pypdf 6.1.1 only
  in the external UI environment; protected venv unchanged.
- No indexed October 8 official report or complete historical archive was found.
  Prospective refresh requires an actual published URL. This late-collected
  historical probe cannot supply pregame backtesting availability. No current
  status, player ID for an ambiguous name, or fallback record was fabricated.

## T016 — provenance-safe optional news — 2026-10-08
- Added stable-ID/name GNews lookup, immutable raw/normalized snapshots, six-hour
  caching, publication/retrieval times and conservative body-only explicit-status
  extraction. Headline-only, negated, speculative and conflicting text remains
  unclassified. Claims never become official/current availability; stale age is
  recomputed even on cache hits. Future/unrelated articles are excluded.
- Three focused tests and full isolated discovery (78 tests) passed; protected
  syntax/notebook validation passed. Actual CLI without credentials exited 1
  with actionable GNEWS_API_KEY error and unknown availability. Fixture-populated
  cached CLI smoke returned unconfirmed `out`, supporting text and source times,
  `current_availability: null`, and `from_cache: true`.
- Live news access remains unverified: no GNews key is available. No credentials,
  production data/model changes or holdout execution. No LLM/article scraping.

## T017 — interpretable contribution scenarios — 2026-10-09
- Added strictly prior same-season rotation estimates, 30-day performance
  weighting, 300-minute shrinkage, explicit [0,1] scenario fractions and
  role-constrained redistribution (48 total / 12 extra minutes per player).
  Unknown availability remains uncertain; official status is never relabeled
  by an override. Missing history/roles and unallocated minutes stay explicit.
- Snapshot/record retrieval provenance and source-as-of must precede the game;
  current rosters cannot join past games. No same-date/future performance enters
  estimates. Features center changes against observed rotation strength rather
  than duplicating its mean; dispersion is the statistics-only candidate.
- Five focused regressions and all 83 isolated tests passed. Protected validator
  passed. Direct synthetic smoke: out guard 0 minutes, same-role replacement 42,
  center unchanged at 30, 18 unallocated minutes; unavailable fraction 0.125.
- No player-adjusted probability, historical effectiveness claim, model fit,
  production replacement or holdout scoring. Constants are declared assumptions.

## T018 — runnable evaluation; historical evidence blocked — 2026-10-09
- Froze T018-v1 before candidate fits; reused T003 baseline/gates and T006 fixed
  calibration bins. Added read-only manifest-based comparison rebuilding T017
  features from verified pregame snapshots, with no retrospective current-roster
  joins, same-date/exposed/future inputs or production promotion.
- Three focused tests and all 86 isolated tests passed; protected validator
  passed. Synthetic archived-snapshot tests exercised both candidate fits and
  confirmed exposed/future manifests are never opened. Missing official reports
  block only the availability comparison; late roster snapshots fail closed.
- Actual `../../venv/bin/python -m scripts.player_feature_evaluation` exited 2:
  missing pregame roster/statistics coverage for all 9,714 retained team/game
  rows. Repository data inventory has no player snapshot archive. Existing live
  snapshots were retrieved in October 2026, after all development games.
- Reproduced baseline before candidates: training 7,286 rows, validation 2,428;
  accuracy 0.6383855024711697, AUC 0.701234092099585, log loss
  0.6299000714756492, Brier 0.21985809688880792. Data hash and feature hash match
  T003; seed 42, train-only scaling, ten calibration bins recorded in CLI output.
- T018 remains pending: no real player candidate comparison or gate pass exists.
  No candidate artifact or feature is accepted/promoted; 2025-26 remains exposed,
  reserved 2026-27 unscored. Future prospective snapshots must not turn that
  holdout into a tuning set. T006 marked done after its existing implementation
  and full independent validation were verified, not reimplemented.

## T019 — scenario context implemented; accepted-feature integration blocked
- Added `InferenceEngine.player_context` and a read-only snapshot adapter for
  roster contributions, explicit scenarios, official versus unconfirmed news,
  provenance and stale/missing warnings. Snapshots must precede observation AND
  game time. Stale official claims remain visible but effective availability is
  unknown; corrupt or failed sources produce actionable errors, not fallback data.
- Four focused tests and all 90 isolated tests passed; protected validator passed.
  Direct scenario smoke retained official `out`, applied 0.5 conditional minutes
  (15), and returned `probability_adjustment: null`. A no-fit/no-predict regression
  exercised the public API. The production 36-feature artifact is unchanged.
- T019 remains pending because T018 has no real-data player-feature gate result.
  No accepted-feature integration or player-adjusted probability is claimed.
  Independent scenario context is implemented for the explicitly authorized UI.
