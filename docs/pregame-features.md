# Canonical pregame features

`src.modeling.pregame_features.build_pregame_features` consumes completed-game
box scores in per-team chronological order. It rejects malformed opponent pairs,
duplicate identities, invalid dates and infinite source statistics. Missing
observations are omitted from rolling means; all-missing windows remain NaN.
Rolling-five means, season wins/counts and elapsed-calendar-day rest use strictly earlier dates
within the supplied season. Every game on the target date is excluded. First-game
history is NaN, not a postgame substitute. Opponents are paired one-to-one.

`team_state` and `matchup_features` are shared with read-only inference. Rest means
calendar days between games, matching the persisted model's training convention,
not full idle days. A July season boundary prevents offseason state carryover.
The source contains outcomes, so it must never be passed directly to a classifier.
Calendar dates do not prove original upstream publication times; this builder is
not a point-in-time source archive. The production artifact was trained separately;
reconstruction does not make historical predictions unbiased backtests.
