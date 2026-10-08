#!/usr/bin/env python3
"""External supervisor. Invoke from a normal terminal, outside Codex sandbox."""
import argparse
from contextlib import contextmanager
import hashlib
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
# Resolve the common checkout when launched from the managed worktree.
if ROOT.name == 'worktree' and ROOT.parent.name == '.automation':
    ROOT = ROOT.parent.parent
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
DEFAULT_OMP_PROVIDER = 'openai-codex'
DEFAULT_OMP_MODEL = 'gpt-5.6-luna'


def agent_command(agent, prompt, cwd, provider=DEFAULT_OMP_PROVIDER,
                  model=DEFAULT_OMP_MODEL):
    if agent == 'codex':
        return ['codex', 'exec', '--sandbox', 'workspace-write',
                '-c', 'approval_policy="never"', '--json', '-C', str(cwd),
                prompt]
    if agent == 'omp':
        return ['omp', '--provider', provider, '--model', model,
                '--cwd', str(cwd), '--mode', 'json', '--no-session',
                '--no-extensions', '--no-skills', '--no-pty',
                '--approval-mode', 'yolo', '-p', prompt]
    raise ValueError(f'Unsupported agent: {agent}')


def verify_agent_log(logfile, agent, provider):
    """Reject provider changes hidden behind a successful agent response."""
    seen_providers = set()
    for line in logfile.read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            event = {'type': 'error', 'message': line}
        reported = event.get('provider')
        if not reported and isinstance(event.get('message'), dict):
            reported = event['message'].get('provider')
        if reported:
            seen_providers.add(reported)
        if ('error' in event or event.get('type') in ('error', 'turn.failed')) and FATAL.search(line):
            raise RuntimeError('Authentication/usage failure; session stopped')
    if agent == 'omp' and seen_providers != {provider}:
        raise RuntimeError(
            f'OMP provider mismatch: requested {provider!r}, observed {sorted(seen_providers)}')


def run(command, cwd, logfile, timeout=120):
    """Bound the entire process group, including grandchildren."""
    with logfile.open('w') as out:
        env = os.environ.copy()
        env['NBA_RUNNER_CHILD'] = '1'
        env['GIT_TERMINAL_PROMPT'] = '0'
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=out,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return proc.wait(timeout=timeout)
        finally:
            # Kill descendants even when the direct child already exited.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            except ProcessLookupError:
                proc.wait()


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
    stage('committing', title)
    git(cwd, 'add', '--', *sorted(paths))
    staged = set(git(cwd, 'diff', '--cached', '--name-only').splitlines())
    if staged != paths:
        raise RuntimeError('Staged files differ from approved task files')
    git(cwd, 'diff', '--cached', '--check')
    git(cwd, 'commit', '-m', title)
    record_path = STATE / 'active-run.json'
    if record_path.exists():
        record = json.loads(record_path.read_text())
        record['commit'] = git(cwd, 'rev-parse', 'HEAD')
        save_record(record)
    stage('pushing', BRANCH)
    if run(['git', 'push', '--set-upstream', 'origin',
            f'HEAD:refs/heads/{BRANCH}'], cwd, logs / 'push.log'):
        raise RuntimeError('Push failed; inspect push.log, repair authentication or reconcile remote manually')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-tasks', type=int, choices=range(1, 4), default=3)
    parser.add_argument('--task-timeout', type=int, default=900)
    parser.add_argument('--agent', choices=('codex', 'omp'), default='omp',
                        help='Agent CLI used for task attempts')
    parser.add_argument('--provider', default=DEFAULT_OMP_PROVIDER,
                        help='OMP provider (default: openai-codex)')
    parser.add_argument('--model', default=DEFAULT_OMP_MODEL,
                        help='OMP model (default: gpt-5.6-luna)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--bootstrap', action='store_true',
                        help='Publish reviewed setup and completed T001 once')
    args = parser.parse_args()
    if not args.provider or not args.model:
        parser.error('provider and model must be non-empty')
    if args.task_timeout < 1:
        parser.error('timeout must be positive')
    if os.environ.get('NBA_RUNNER_CHILD'):
        raise RuntimeError('Recursive runner launch blocked; run from a normal terminal')
    STATE.mkdir(exist_ok=True, mode=0o700)
    entered = False
    try:
        with runner_lock(STATE):
            entered = True
            session(args)
    except (Exception, KeyboardInterrupt) as exc:
        if not entered:
            stage('blocked', str(exc))
            logs = STATE / 'logs' / f'{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}'
            logs.mkdir(parents=True, exist_ok=True, mode=0o700)
            (logs / 'summary.json').write_text(json.dumps(
                {'completed_tasks': [], 'blocker': str(exc)}, indent=2))
        raise


@contextmanager
def runner_lock(state):
    # Never unlink the lock inode: stale metadata is safe once flock succeeds.
    with (state / 'runner.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Active runner lock; wait for it or stop its recorded PID')
        (state / 'runner.pid').write_text(str(os.getpid()))
        try:
            yield
        finally:
            (state / 'runner.pid').unlink(missing_ok=True)


def stage(name, detail=''):
    print(f'{name}: {detail}', flush=True)


def save_record(record):
    target = STATE / 'active-run.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2))
    temporary.replace(target)


def fingerprints(cwd, paths):
    result = {}
    for name in paths:
        path = cwd / name
        if path.is_symlink():
            raise RuntimeError(f'Unsafe symlink: {name}')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def ownership(cwd, record):
    if not record or record.get('complete'):
        raise RuntimeError('Dirty files have no unfinished run record; inspect ownership manually')
    if git(cwd, 'rev-parse', 'HEAD') != record['base']:
        raise RuntimeError('Run base differs from HEAD; inspect history before retrying')
    if (cwd / 'TASKS.md').read_text() != record['manifest']:
        raise RuntimeError('Task manifest changed outside the recorded run; review manually')
    pending = {task: sorted(files | {'PROGRESS.md'}) for task, _, files in tasks(record['manifest'])}
    if pending.get(record['task']) != sorted(record['allowed']):
        raise RuntimeError('Recorded allowlist differs from task manifest; inspect manually')
    paths = changed(cwd)
    try:
        if paths:
            scope(paths, set(record['allowed']), cwd)
    except RuntimeError as exc:
        raise RuntimeError(f'{exc}; ownership uncertain, inspect retained files manually') from exc
    # After a supervisor checkpoint, any different bytes require manual review.
    if record.get('snapshot') is not None and fingerprints(cwd, paths) != record['snapshot']:
        raise RuntimeError('Dirty files differ from recorded checkpoint; ownership uncertain, review manually')
    return paths


def execute_task(args, cwd, logs, record, recovery=False):
    deadline = time.monotonic() + args.task_timeout
    prompt = (f"Complete only {record['task']}: {record['title']}. Read AGENTS.md and TASKS.md. "
              f"Only edit these files: {record['allowed']}. Do not edit TASKS.md. "
              f"No Git mutations or runner launches. Use existing Python {PYTHON}. "
              'No packages, parallel workers, advisor calls, model/artifact writes. '
              'Preserve chronological evaluation rules. Record evidence in PROGRESS.md. '
              f"Diagnose failures using {record.get('logs', logs)} and {logs}.")
    while True:
        if recovery:
            if record['repairs'] >= 2:
                raise RuntimeError('Two recovery attempts exhausted; review retained changes and logs manually')
            record['repairs'] += 1
            stage('repairing', f"{record['task']} attempt {record['repairs']}/2")
        else:
            stage('agent working', record['task'])
        # Persist before launch so an interrupted agent has provenance.
        record['snapshot'] = None
        save_record(record)
        logfile = logs / f"{record['task']}-attempt-{record['repairs']}.jsonl"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Task deadline exceeded; inspect retained run before restarting')
        rc = run(agent_command(args.agent, prompt, cwd, args.provider, args.model), cwd, logfile, remaining)
        verify_agent_log(logfile, args.agent, args.provider)
        ownership(cwd, record)
        record['snapshot'] = fingerprints(cwd, changed(cwd))
        save_record(record)
        stage('validating', record['task'])
        checks = validate(cwd, logs, f"{record['task']}-{record['repairs']}", deadline)
        if rc == 0 and checks and changed(cwd):
            break
        recovery = True
        prompt += ' Diagnose and repair the failed independent checks; preserve validation.'
    # Validate all task files before the supervisor updates status.
    ownership(cwd, record)
    (cwd / 'TASKS.md').write_text(record['manifest'].replace(
        f"## {record['task']} | pending |", f"## {record['task']} | done |", 1))
    paths = changed(cwd)
    scope(paths, set(record['allowed']) | {'TASKS.md'}, cwd)
    record['phase'] = 'publishing'
    record['publish_snapshot'] = fingerprints(cwd, paths)
    save_record(record)
    publish(cwd, paths, f"{record['task']}: {record['title']}", logs)
    record['complete'] = True
    save_record(record)
    stage('completed', record['task'])
    return record['task']


def resume_publication(cwd, logs, record):
    head = git(cwd, 'rev-parse', 'HEAD')
    if head == record['base']:
        paths = changed(cwd)
        if fingerprints(cwd, paths) != record['publish_snapshot']:
            raise RuntimeError('Publication files changed; review ownership manually')
        stage('validating', record['task'])
        if not validate(cwd, logs, 'resume-publish'):
            raise RuntimeError('Publication revalidation failed; review logs and retained files')
        publish(cwd, paths, f"{record['task']}: {record['title']}", logs)
    else:
        if changed(cwd) or git(cwd, 'rev-parse', 'HEAD^') != record['base']:
            raise RuntimeError('Unrecognized commit or dirty files after publication; inspect manually')
        paths = set(git(cwd, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines())
        if fingerprints(cwd, paths) != record['publish_snapshot']:
            raise RuntimeError('Commit differs from validated publication; review manually')
        stage('validating', record['task'])
        if not validate(cwd, logs, 'resume-push'):
            raise RuntimeError('Committed work failed revalidation; inspect logs manually')
        stage('pushing', BRANCH)
        rc = run(['git', 'push', '--set-upstream', 'origin', f'HEAD:refs/heads/{BRANCH}'],
                 cwd, logs / 'push.log')
        if rc:
            raise RuntimeError('Push failed; inspect push.log, repair authentication or reconcile remote manually')
    record['complete'] = True
    save_record(record)
    stage('completed', record['task'])


def session(args):
    completed = []
    blocker = None
    logs = STATE / 'logs' / f'{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}'
    logs.mkdir(parents=True, mode=0o700)
    try:
        session_work(args, logs, completed)
    except (Exception, KeyboardInterrupt) as exc:
        blocker = str(exc) or "Interrupted; inspect active-run.json and restart"
        stage("blocked", blocker)
        raise
    finally:
        (logs / "summary.json").write_text(json.dumps(
            {"completed_tasks": completed, "blocker": blocker}, indent=2))


def session_work(args, logs, completed):
    print(f'Logs: {logs}', flush=True)
    agent_binary = 'codex' if args.agent == 'codex' else 'omp'
    if not PYTHON.exists() or not shutil.which(agent_binary):
        raise RuntimeError(f'Existing venv and {agent_binary} are required')
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
    if git(cwd, 'branch', '--show-current') != BRANCH:
        raise RuntimeError(f'Wrong branch; expected {BRANCH}. Inspect worktree manually')
    record_path = STATE / 'active-run.json'
    record = json.loads(record_path.read_text()) if record_path.exists() else None
    if record and not record.get('complete') and record.get('phase') == 'publishing':
        if record['repairs'] >= 2:
            raise RuntimeError('Two recovery attempts exhausted; inspect retained publication manually')
        record['repairs'] += 1
        save_record(record)
        resume_publication(cwd, logs, record)
        completed.append(record['task'])
    elif changed(cwd):
        ownership(cwd, record)
        completed.append(execute_task(args, cwd, logs, record, recovery=True))
    elif record and not record.get('complete'):
        if git(cwd, 'rev-parse', 'HEAD') != record['base'] or (cwd / 'TASKS.md').read_text() != record['manifest']:
            raise RuntimeError('Interrupted run history/manifest changed; review manually')
        completed.append(execute_task(args, cwd, logs, record, recovery=True))
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
    remaining_tasks = args.max_tasks - len(completed)
    for task_id, title, files in tasks((cwd / 'TASKS.md').read_text())[:remaining_tasks]:
        if git(cwd, 'branch', '--show-current') != BRANCH:
            raise RuntimeError(f'Wrong branch; expected {BRANCH}. Inspect manually')
        if changed(cwd):
            raise RuntimeError('Unexpected dirty files before task; inspect manually')
        stage('task selected', f'{task_id}: {title}')
        record = {'task': task_id, 'title': title, 'allowed': sorted(files | {'PROGRESS.md'}),
                  'base': git(cwd, 'rev-parse', 'HEAD'), 'manifest': (cwd / 'TASKS.md').read_text(),
                  'repairs': 0, 'complete': False, 'logs': str(logs)}
        save_record(record)
        completed.append(execute_task(args, cwd, logs, record))


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f'Stopped: {exc}', file=sys.stderr)
        sys.exit(1)
