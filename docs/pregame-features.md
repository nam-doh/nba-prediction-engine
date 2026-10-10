# Canonical pregame features

`src.modeling.pregame_features.build_pregame_features` consumes completed-game
box scores in per-team chronological order and requires team abbreviations plus
the provider's `MATCHUP` orientation. It rejects malformed opponent pairs,
duplicate identities, invalid dates, infinite statistics and inconsistent
opponent abbreviations. Each paired row receives the correct home indicator;
neutral-site games with both matchup labels `@` retain `HOME_GAME=0` for both.
Missing source observations are omitted from rolling means; all-missing windows
remain NaN.

Rolling-five, previous win/points, prior wins/game count, winning streak,
season win percentage/game number and elapsed-calendar-day rest use strictly
earlier dates within the supplied season. All games for a team on one date share
the exact same pre-date state, including doubleheaders. July starts a new season;
first-season history is NaN. Opponents are joined one-to-one.

`team_state` and `matchup_features` are shared with read-only inference. Rest
matches the persisted model's elapsed-calendar-day convention, not full idle
days. The source contains outcomes, so it must never be passed directly to a
classifier. Calendar dates do not prove upstream publication times; this builder
is not a point-in-time source archive, and reconstruction does not make historical
predictions unbiased backtests.

Full supplied-data smoke reconstructed 12,300 rows / 6,150 games; 6,140 home
indicators and 10 neutral-site games. No file was written.
