# Unattended improvements

Run from the original repository root in a normal terminal, outside Codex's
sandbox. No recurring scheduler is installed. The selected CLI must already be
authenticated; never put credentials in this repository. The existing venv is
reused.

```sh
venv/bin/python scripts/improve.py --dry-run --max-tasks 3
venv/bin/python scripts/improve.py --max-tasks 3
venv/bin/python scripts/improve.py --agent omp --provider openai-codex \
  --model gpt-5.6-luna --max-tasks 3
```

`--agent` accepts `codex` or `omp` (the default). OMP uses its supported
non-interactive `-p/--print` mode, JSON output, an isolated worktree, and
explicit `--provider`/`--model` flags. The default is the ChatGPT
`openai-codex` provider with the installed `gpt-5.6-luna` model. The supervisor
checks OMP's reported provider and stops on a mismatch; it never falls back to
another provider. Optional advisor and worker calls are disabled by default and
the task prompt forbids parallel workers. Change provider/model only by an
explicit command-line choice.

The runner uses `.automation/worktree` on `automation/nba-improvements`, an
exclusive flock, and `.automation/logs/<timestamp>-<pid>/`. Original working
changes are never copied into the worktree. New task files are explicitly
allowlisted. Codex attempts use `codex exec --sandbox workspace-write`; Codex
privileged requests fail rather than prompting. OMP attempts use its print mode
inside the isolated worktree, and the task prompt forbids Git mutations,
advisor calls, and worker calls. Git commit/push are executed only by this
external supervisor. No force-push or merge commands exist. Non-fast-forward
pushes stop the session; inspect and reconcile manually. A failed push leaves
the validated local commit; after review, retry `git -C .automation/worktree push origin HEAD:automation/nba-improvements`.

Default deadline is 900 seconds per task, including attempts and validation.
There are at most two repairs after the first attempt; timeout or authentication/
usage failures stop immediately. Independent checks have 300-second ceilings;
the task deadline is also checked after validation. Logs are local and may
contain source code; do not publish them. Failed work is retained. Before launch the runner checks the exclusive lock,
automation branch, and changed paths. `.automation/active-run.json` records the
base commit, original manifest, allowed files, log directory, repair count, and
validation checkpoints. Identifiable interrupted work is sent to the configured
agent for diagnosis, repair, and independent validation. At most two repairs are
permitted across restarts. Successful recovery counts toward the existing task
limit, then pending tasks continue. An interrupted commit/push is revalidated
against the recorded file hashes before publication is retried.

A dirty worktree without a matching unfinished record, changes outside its
allowlist, a changed manifest/base, or edits after a checkpoint block execution.
Allowlisted files during an interrupted agent invocation are attributed to that
record; do not edit the managed worktree while a run is active. Records are
local provenance, not a security boundary against deliberate modification.
Legacy logs alone are not automatically treated as ownership evidence.
No changes are reset, deleted, or force-pushed. Review uncertain work manually;
this runner does not stash or commit user changes. Authentication/provider
failures stop immediately. Fix authentication in the normal CLI, then restart;
non-fast-forward pushes require manual reconciliation.

Live output reports task selected, agent working, validating, repairing,
committing, pushing, completed, and blocked. Each session saves
`summary.json` with completed task IDs and its blocker. Child process groups
are cleaned up on success, failure, timeout, and interruption. Stale PID metadata
is replaced only after acquiring flock; an actively held lock always blocks.
The persistent lock inode is never deleted. Agents inherit `NBA_RUNNER_CHILD=1`
and cannot recursively invoke the runner.

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


## Launch the reviewed recovery runner

The original checkout may contain older user-owned runner files. To execute the
reviewed implementation without overwriting them, run this exact command from
the original repository root:

```sh
venv/bin/python .automation/worktree/scripts/improve.py --agent omp --provider openai-codex --model gpt-5.6-luna --max-tasks 3 --task-timeout 900
```

The script resolves the original checkout's existing venv and common automation
state even when invoked from the managed worktree. Do not launch a second copy
from a worker. Uncommitted UI backlog changes in `TASKS.md` and `PROGRESS.md`
were deliberately preserved during the recovery rollout; they have no new run
record and will block launch until their owner resolves them. T006 code was
validated and published, but its pending status is preserved in the user-dirty
manifest. Reconcile that status before executing the queue to avoid duplication.
