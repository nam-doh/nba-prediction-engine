# Unattended improvements

Run from the original repository root in a normal terminal, outside Codex's
sandbox. No recurring scheduler is installed. Codex CLI must already be signed
in; never put credentials in this repository. The existing venv is reused.

```sh
venv/bin/python scripts/improve.py --dry-run --max-tasks 3
venv/bin/python scripts/improve.py --max-tasks 3
```

The runner uses `.automation/worktree` on `automation/nba-improvements`, an
exclusive flock, and `.automation/logs/<timestamp>-<pid>/`. Original working
changes are never copied into the worktree. New task files are explicitly
allowlisted. Agent attempts use `codex exec --sandbox workspace-write` with
approval_policy=never; privileged requests fail rather than prompting. Git
commit/push are executed only by this external supervisor. No force-push or
merge commands exist. Non-fast-forward pushes stop the session; inspect and
reconcile manually. A failed push leaves the validated local commit; after
review, retry `git -C .automation/worktree push origin HEAD:automation/nba-improvements`.

Default deadline is 900 seconds per task, including attempts and validation.
There are at most two repairs after the first attempt; timeout or authentication/
usage failures stop immediately. Independent checks have 300-second ceilings;
the task deadline is also checked after validation. Logs are local and may
contain source code; do not publish them. Failed work stays for review; restarting
refuses a dirty worktree. Inspect and repair it manually without discarding work.

Stop with Ctrl-C in the foreground or, from this repository root:

```sh
kill -TERM "$(cat .automation/runner.pid)"
```

The active child process group is terminated; the lock is released automatically.
Do not delete the lock file to stop a process. Review leftover work before restart.
`--bootstrap` is a one-time explicit publication of the fixed reviewed setup
manifest and completed T001; it does not run Codex. Do not use it for later tasks.

Task acceptance requires meaningful regression tests and recorded evidence;
passing structural checks alone does not establish model improvement. See
AGENTS.md for baseline, temporal validation, and untouched holdout requirements.
Tracked historical CSV/HTML/pickle assets remain in history; ignore rules keep
new artifacts out, and task scope prevents automated changes to existing ones.
