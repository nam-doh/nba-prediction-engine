# Runner recovery review

T006 implementation: validated and pushed as a552db2. Runner recovery: validated and pushed as a6d9f4e on automation/nba-improvements.

44 unittest regressions passed; scripts/validate.py and the independent leakage audit passed. Recovery tests cover interrupted work, validation failures, persistent repair limits, user-owned edits, stale/active locks, recursive launch rejection, publication recovery, queue continuation, and wrong branches. The actual launch blocked before OMP on the preserved user-owned manifest/progress edits and released its lock.

User-owned TASKS.md and PROGRESS.md remain byte-preserved and uncommitted. T006 remains pending in that manifest. Owner resolution is required before unattended launch. The original checkout is untouched. No live OMP recovery was executed; tests mock worker/publication transitions. No dataset, model, notebook, credentials, venv, allowlist, or validation-command changes. Existing 2025-26 exposure and chronological evaluation rules remain in force.
