#!/usr/bin/env python3
"""External supervisor. Invoke from a normal terminal, outside Codex sandbox."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.automation'
BRANCH = 'automation/nba-improvements'
PYTHON = ROOT / 'venv/bin/python'
BOOTSTRAP = ['.gitignore', 'AGENTS.md', 'TASKS.md', 'PROGRESS.md',
             'scripts/improve.py', 'scripts/validate.py', 'docs/automation.md',
             'tests/test_runner.py', 'src/modeling/chronological.py',
             'tests/test_chronological.py']
FATAL = re.compile(r'(?i)(unauthorized|authentication failed|invalid.api.key|'
                   r'usage.limit|rate.limit|quota.exceeded|insufficient_quota|'
                   r'too many requests|token.expired|refresh.token|http\s*(401|403|429))')


def run(command, cwd, logfile, timeout=120):
    """Bound the entire process group, including grandchildren."""
    with logfile.open('w') as out:
        proc = subprocess.Popen(command, cwd=cwd, stdout=out,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return proc.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            raise


def git(cwd, *args):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def changed(cwd):
    paths = set()
    for args in [('diff', '--name-only', '-z'),
                 ('diff', '--cached', '--name-only', '-z'),
                 ('ls-files', '--others', '--exclude-standard', '-z')]:
        raw = subprocess.check_output(['git', *args], cwd=cwd)
        paths.update(p.decode() for p in raw.split(b'\0') if p)
    return paths


def tasks(text):
    result = []
    for match in re.finditer(r'^## (T\d+) \| pending \| ([^\n]+)\nFiles: ([^\n]+)', text, re.M):
        result.append((match[1], match[2], set(match[3].split(', '))))
    return result


def scope(paths, allowed, cwd):
    if not paths or not paths <= allowed:
        raise RuntimeError(f'Unexpected or empty change set: {sorted(paths - allowed)}')
    for name in paths:
        path = cwd / name
        if path.is_symlink() or (path.exists() and path.stat().st_size > 1_000_000):
            raise RuntimeError(f'Unsafe/large file: {name}')


def validate(cwd, logs, prefix, deadline=None):
    commands = [[str(PYTHON), '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                [str(PYTHON), str(cwd / 'scripts/validate.py')]]
    if (cwd / 'scripts/audit_leakage.py').exists():
        commands.append([str(PYTHON), str(cwd / 'scripts/audit_leakage.py')])
    passed = True
    for i, cmd in enumerate(commands):
        remaining = 300 if deadline is None else min(300, deadline - time.monotonic())
        if remaining <= 0:
            raise RuntimeError('Task deadline exceeded')
        passed = (run(cmd, cwd, logs / f'{prefix}-check-{i}.log', remaining) == 0) and passed
    return passed


def publish(cwd, paths, title, logs):
    if git(cwd, 'branch', '--show-current') != BRANCH:
        raise RuntimeError('Wrong branch')
    git(cwd, 'add', '--', *sorted(paths))
    staged = set(git(cwd, 'diff', '--cached', '--name-only').splitlines())
    if staged != paths:
        raise RuntimeError('Staged files differ from approved task files')
    git(cwd, 'diff', '--cached', '--check')
    git(cwd, 'commit', '-m', title)
    # Deliberately outside codex exec: no force, no merge, exact refspec.
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    with (logs / 'push.log').open('a') as out:
        subprocess.run(['git', 'push', '--set-upstream', 'origin',
                        f'HEAD:refs/heads/{BRANCH}'], cwd=cwd, env=env,
                       stdout=out, stderr=subprocess.STDOUT, timeout=120, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-tasks', type=int, choices=range(1, 4), default=3)
    parser.add_argument('--task-timeout', type=int, default=900)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--bootstrap', action='store_true',
                        help='Publish reviewed setup and completed T001 once')
    args = parser.parse_args()
    if args.task_timeout < 1:
        parser.error('timeout must be positive')
    STATE.mkdir(exist_ok=True, mode=0o700)
    with (STATE / 'runner.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another runner holds the lock')
        (STATE / 'runner.pid').write_text(str(os.getpid()))
        try:
            session(args)
        finally:
            (STATE / 'runner.pid').unlink(missing_ok=True)


def session(args):
    logs = STATE / 'logs' / f'{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}'
    logs.mkdir(parents=True, mode=0o700)
    print(f'Logs: {logs}', flush=True)
    if not PYTHON.exists() or not shutil.which('codex'):
        raise RuntimeError('Existing venv and codex are required')
    if args.dry_run:
        plan = tasks((ROOT / 'TASKS.md').read_text())[:args.max_tasks]
        (logs / 'plan.json').write_text(json.dumps(plan, default=sorted, indent=2))
        if not validate(ROOT, logs, 'dry-run'):
            raise RuntimeError('Dry-run validation failed')
        print('Dry run passed: no agent execution, branch mutation, commits or pushes.')
        return
    cwd = STATE / 'worktree'
    if not cwd.exists():
        exists = subprocess.run(['git', 'show-ref', '--verify', '--quiet',
                                  f'refs/heads/{BRANCH}'], cwd=ROOT).returncode == 0
        git(ROOT, 'worktree', 'add', *([] if exists else ['-b', BRANCH]), str(cwd),
            *([BRANCH] if exists else ['HEAD']))
    if git(cwd, 'branch', '--show-current') != BRANCH or changed(cwd):
        raise RuntimeError('Worktree is dirty or wrong branch; inspect it before restarting')
    if args.bootstrap:
        if (cwd / 'scripts/improve.py').exists():
            raise RuntimeError('Bootstrap already installed; use a normal session')
        for name in BOOTSTRAP:
            target = cwd / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        if not validate(cwd, logs, 'bootstrap'):
            raise RuntimeError('Bootstrap validation failed')
        scope(changed(cwd), set(BOOTSTRAP), cwd)
        publish(cwd, changed(cwd), 'Set up unattended improvements and chronological split guard', logs)
        return
    for task_id, title, files in tasks((cwd / 'TASKS.md').read_text())[:args.max_tasks]:
        original_tasks = (cwd / 'TASKS.md').read_text()
        base = git(cwd, 'rev-parse', 'HEAD')
        allowed = files | {'PROGRESS.md'}
        prompt = (f'Complete only {task_id}: {title}. Read AGENTS.md and TASKS.md. '
                  f'Only edit these files: {sorted(allowed)}. Do not edit TASKS.md. '
                  'No Git mutations. Record acceptance evidence in PROGRESS.md.')
        deadline = time.monotonic() + args.task_timeout
        for attempt in range(3):  # initial attempt plus at most two repairs
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Task deadline exceeded')
            logfile = logs / f'{task_id}-attempt-{attempt}.jsonl'
            rc = run(['codex', 'exec', '--sandbox', 'workspace-write',
                      '-c', 'approval_policy="never"', '--json', '-C', str(cwd), prompt],
                     cwd, logfile, remaining)
            # Check structured error events, not successful prose mentioning limits.
            for line in logfile.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    event = {'type': 'error', 'message': line}
                if ('error' in event or event.get('type') in ('error', 'turn.failed')) and FATAL.search(line):
                    raise RuntimeError('Authentication/usage failure; session stopped')
            if git(cwd, 'rev-parse', 'HEAD') != base:
                raise RuntimeError('Agent changed Git history')
            if (cwd / 'TASKS.md').read_text() != original_tasks:
                raise RuntimeError('Agent changed task manifest')
            scope(changed(cwd), allowed, cwd)
            checks = validate(cwd, logs, f'{task_id}-{attempt}', deadline)
            if time.monotonic() > deadline:
                raise RuntimeError('Task deadline exceeded during validation')
            if rc == 0 and checks:
                break
            prompt += f' Repair only this task. Previous attempt failed; inspect {logs} for evidence.'
        else:
            raise RuntimeError('Two repairs exhausted; changes retained for review')
        (cwd / 'TASKS.md').write_text(original_tasks.replace(
            f'## {task_id} | pending |', f'## {task_id} | done |', 1))
        scope(changed(cwd), allowed | {'TASKS.md'}, cwd)
        publish(cwd, changed(cwd), f'{task_id}: {title}', logs)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f'Stopped: {exc}', file=sys.stderr)
        sys.exit(1)
