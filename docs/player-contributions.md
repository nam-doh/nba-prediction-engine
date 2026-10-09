# Interpretable player rotation scenarios

`estimate_contributions` accepts verified roster/statistics/optional official
availability snapshots, an NBA team ID and timezone-aware hypothetical game time.
Use `SnapshotStore.read` at file boundaries. Every snapshot must have been retrieved
strictly before the game; source-as-of cannot follow retrieval. Record timestamps
must agree with the snapshot. Current rosters cannot be replayed into history.
Performance excludes every game on/after the target calendar date and resets each
July season. Stable historical team IDs prevent traded-player history from being
silently assigned to a new team. Missing same-season rotations fail closed.

Expected minutes average the last ten observed team games, including zero minutes
for a roster member absent from a game. This is an observed-rotation continuation,
not evidence of health. Out means zero; an explicit scenario fraction in [0,1]
can override any player without changing their official status. All other statuses
retain conditional rotation minutes and uncertainty unless explicitly available.

Strength proxy per minute is points + 0.7 rebounds + 0.7 assists + steals + blocks
minus turnovers. Thirty-day half-life weights prior games; 300 weighted prior
minutes shrink each player toward the team's observed production rate. These
constants are declared assumptions, not tuned parameters or causal impact ratings.
No observed performance means null strength, zero rotation minutes and a warning
field, not an invented replacement player.

Removed minutes redistribute only to observed players with overlapping G/F/C
roles, capped at 48 total and 12 extra minutes each. Unknown positions do not gain
invented eligibility. Unfillable minutes remain explicit; incomplete rosters do
not magically total 240. Overtime inflation is capped to a 240-minute rotation.
Features are rotation-strength dispersion (not another team mean), the centered
strength change from the baseline rotation, unavailable-minute fraction and
unallocated-minute fraction. This limits duplication of existing team strength,
but only chronological evaluation can establish incremental value.

Output includes per-player minutes/strength/sample size, official versus scenario
state, unknown minutes, rotation coverage, provenance and stale/missing warnings.
It never computes a player-adjusted win probability. Synthetic temporal, scenario,
role-cap, shrinkage and provenance regressions plus a direct smoke are verified;
no real historical injury-backed performance result exists yet.
