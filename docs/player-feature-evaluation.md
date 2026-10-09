# Player evaluation protocol T018-v1

Frozen before any candidate fit: reuse T003 seed 42, logistic regression and
train-only StandardScaler. Training is [2021-07-01, 2024-07-01); development
validation is [2024-07-01, 2025-07-01). Both team rows and every same-date game
remain together. The exposed 2025-26 period and reserved [2026-07-01, 2027-07-01)
are neither fitted nor scored. No tuning, calibration or artifact promotion.

Compare baseline, baseline plus rotation-strength spread, then baseline plus all
T017 scenario features, on the exact same retained games. Numerical gates remain:
strictly lower validation log loss, Brier no worse, ROC AUC no more than 0.005 lower
than baseline. Report all four metrics and fixed T006 calibration bins. Passing
these gates is evidence only; no model may be installed by this command.

No missing-history selection after seeing outcomes: each retained team/game needs
an archived roster and player statistics snapshot retrieved strictly before its
game-date midnight UTC. T017 rebuilds contributions from those snapshots, not
user-supplied feature columns. Availability comparison additionally requires an
official pregame snapshot covering that game's team/date. Missing coverage blocks
the relevant comparison; unknown player status remains unknown, not healthy.
Snapshot hashes and the ordered manifest are recorded with data/feature hashes,
versions, dates, counts and seed. Current roster or late-retrieved historical logs
cannot stand in for a point-in-time archive.

Run `python -m scripts.player_feature_evaluation --manifest PATH --snapshot-dir
PATH`. Manifest JSON is a list of objects with `game_id`, `team_id`, and paths
`roster`, `statistics`, optionally `availability`, relative to the snapshot root.
Without a manifest the command reports the reproducible baseline and exact missing
coverage blocker, exits 2, and never fits a candidate. Paths must stay within the
verified immutable snapshot store. Reports go to stdout only.

Historical roster/statistics publication-time archives and complete injury-report
coverage are currently absent. The October 2026 live snapshots were collected too
late for development games. Collect prospective snapshots, but do not repurpose
the frozen holdout to tune this protocol; authorize a separate future development
period before evaluating newly collected prospective data. Scenario UI outputs
are not validated player-adjusted predictions.
