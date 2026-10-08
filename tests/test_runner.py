import fcntl
import subprocess
import tempfile
import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch
from scripts import improve
from pathlib import Path
from scripts.improve import (FATAL, agent_command, run, scope, tasks,
                              verify_agent_log)


class RunnerTests(unittest.TestCase):
    def test_queue(self):
        self.assertEqual(tasks('## T001 | pending | Guard\nFiles: a, b')[0][2], {'a', 'b'})
        self.assertEqual(tasks('## T001 | done | Guard\nFiles: a'), [])

    def test_fatal(self):
        for message in ('HTTP 401', 'usage limit reached', 'insufficient_quota',
                        'authentication failed', 'rate limit exceeded'):
            self.assertTrue(FATAL.search(message))


    def test_omp_command_uses_print_mode_with_explicit_selection(self):
        provider = 'openai-codex'
        model = 'gpt-5.6-luna'
        command = agent_command('omp', 'prompt', Path('/tmp/worktree'),
                                provider, model)
        self.assertEqual(command, [
            'omp', '--provider', provider, '--model', model,
            '--cwd', '/tmp/worktree', '--mode', 'json', '--no-session',
            '--no-extensions', '--no-skills', '--no-pty',
            '--approval-mode', 'yolo', '-p', 'prompt',
        ])
        self.assertNotIn('--advisor', command)

    def test_omp_log_must_report_requested_provider(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'omp.jsonl'
            log.write_text('{"provider":"openai-codex"}\n')
            verify_agent_log(log, 'omp', 'openai-codex')
            log.write_text('{"provider":"other"}\n')
            with self.assertRaises(RuntimeError):
                verify_agent_log(log, 'omp', 'openai-codex')

    def test_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError):
                scope({'secret'}, {'allowed'}, Path(folder))
            with self.assertRaises(RuntimeError):
                scope(set(), {'allowed'}, Path(folder))

    def test_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(subprocess.TimeoutExpired):
                run(['/bin/sleep', '10'], folder, Path(folder) / 'log', 0.05)

    def test_lock(self):
        with tempfile.TemporaryFile() as first:
            fcntl.flock(first, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Separate open file descriptions contend, even within one process.
            with tempfile.NamedTemporaryFile() as named:
                with open(named.name, 'w') as a, open(named.name, 'w') as b:
                    fcntl.flock(a, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(b, fcntl.LOCK_EX | fcntl.LOCK_NB)


class RecoveryTests(unittest.TestCase):
    def test_stale_pid_is_replaced_but_live_lock_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            (state / 'runner.pid').write_text('99999999')
            with improve.runner_lock(state):
                self.assertNotEqual((state / 'runner.pid').read_text(), '99999999')
                with self.assertRaisesRegex(RuntimeError, 'Active runner'):
                    with improve.runner_lock(state):
                        pass
            self.assertFalse((state / 'runner.pid').exists())
            self.assertTrue((state / 'runner.lock').exists())

    def test_dirty_ownership_requires_record_scope_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd = Path(folder)
            manifest = '## T999 | pending | Example\nFiles: a'
            (cwd / 'TASKS.md').write_text(manifest)
            (cwd / 'a').write_text('automation')
            record = dict(task='T999', base='head', manifest=manifest, allowed=['a', 'PROGRESS.md'], complete=False)
            with patch.object(improve, 'git', return_value='head'), patch.object(improve, 'changed', return_value={'a'}):
                self.assertEqual(improve.ownership(cwd, record), {'a'})
                with self.assertRaisesRegex(RuntimeError, 'no unfinished'):
                    improve.ownership(cwd, None)
                record['snapshot'] = improve.fingerprints(cwd, {'a'})
                (cwd / 'a').write_text('user edit')
                with self.assertRaisesRegex(RuntimeError, 'ownership uncertain'):
                    improve.ownership(cwd, record)
            with patch.object(improve, 'git', return_value='head'), patch.object(improve, 'changed', return_value={'user.txt'}):
                with self.assertRaises(RuntimeError):
                    improve.ownership(cwd, record)

    def exercise(self, checks, recovery=False, repairs=0):
        with tempfile.TemporaryDirectory() as folder:
            cwd = Path(folder)
            manifest = '## T999 | pending | Example\nFiles: a'
            (cwd / 'TASKS.md').write_text(manifest)
            (cwd / 'a').write_text('unfinished')
            record = dict(task='T999', title='Example', allowed=['a', 'PROGRESS.md'],
                          base='head', manifest=manifest, repairs=repairs, complete=False)
            args = SimpleNamespace(task_timeout=30, agent='omp', provider='openai-codex', model='gpt-5.6-luna')
            with patch.object(improve, 'STATE', cwd), patch.object(improve, 'run', return_value=0) as agent, patch.object(improve, 'verify_agent_log'), patch.object(improve, 'git', return_value='head'), patch.object(improve, 'changed', return_value={'a'}), patch.object(improve, 'validate', side_effect=checks) as validation, patch.object(improve, 'publish') as publish:
                try:
                    improve.execute_task(args, cwd, cwd, record, recovery)
                except RuntimeError:
                    self.assertFalse(publish.called)
                    self.assertEqual(record['repairs'], 2)
                    return agent.call_count, validation.call_count
                self.assertTrue(publish.called)
                self.assertIn('| done |', (cwd / 'TASKS.md').read_text())
                self.assertTrue(json.loads((cwd / 'active-run.json').read_text())['complete'])
                return agent.call_count, validation.call_count

    def test_interrupted_task_invokes_repair_then_independent_validation(self):
        self.assertEqual(self.exercise([True], recovery=True), (1, 1))

    def test_failed_validation_repairs_before_publish(self):
        self.assertEqual(self.exercise([False, True]), (2, 2))

    def test_recovery_budget_persists_and_never_publishes_failures(self):
        self.assertEqual(self.exercise([False, False, False]), (3, 3))
        self.assertEqual(self.exercise([], recovery=True, repairs=2), (0, 0))

    def test_recursive_launch_rejected_before_lock(self):
        with patch.dict(improve.os.environ, {'NBA_RUNNER_CHILD': '1'}), patch('sys.argv', ['improve.py']), patch.object(improve, 'runner_lock') as lock:
            with self.assertRaisesRegex(RuntimeError, 'Recursive'):
                improve.main()
            lock.assert_not_called()

    def test_interrupted_push_revalidates_exact_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd = Path(folder)
            (cwd / 'a').write_text('validated')
            record = dict(task='T999', title='Example', base='base',
                          publish_snapshot=improve.fingerprints(cwd, {'a'}))
            def fake_git(_cwd, *args):
                return {'rev-parse': 'head' if args[-1] == 'HEAD' else 'base',
                        'diff-tree': 'a'}[args[0]]
            with patch.object(improve, 'git', side_effect=fake_git), patch.object(improve, 'changed', return_value=set()), patch.object(improve, 'validate', return_value=True) as validation, patch.object(improve, 'run', return_value=0) as push, patch.object(improve, 'save_record'):
                improve.resume_publication(cwd, cwd, record)
                validation.assert_called_once()
                self.assertEqual(push.call_args.args[0][-1], 'HEAD:refs/heads/automation/nba-improvements')
                self.assertTrue(record['complete'])

    def test_publication_changed_by_user_never_pushes(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd = Path(folder)
            (cwd / 'a').write_text('user')
            record = dict(task='T999', title='Example', base='base', publish_snapshot={'a': 'old'})
            with patch.object(improve, 'git', return_value='base'), patch.object(improve, 'changed', return_value={'a'}), patch.object(improve, 'run') as push:
                with self.assertRaisesRegex(RuntimeError, 'ownership'):
                    improve.resume_publication(cwd, cwd, record)
                push.assert_not_called()

    def test_blocked_session_saves_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(improve, 'STATE', Path(folder)), patch.object(improve, 'session_work', side_effect=RuntimeError('ownership uncertain')):
                with self.assertRaises(RuntimeError):
                    improve.session(None)
                summary = next(Path(folder).glob('logs/*/summary.json'))
                self.assertEqual(json.loads(summary.read_text()), {'completed_tasks': [], 'blocker': 'ownership uncertain'})

    def test_child_inherits_recursion_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'child.log'
            self.assertEqual(run([str(improve.PYTHON), '-c', 'import os; print(os.environ["NBA_RUNNER_CHILD"])'], folder, log), 0)
            self.assertEqual(log.read_text().strip(), '1')

    def test_successful_recovery_continues_pending_queue_within_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            cwd = state / 'worktree'
            cwd.mkdir()
            manifest = '## T998 | pending | Interrupted\nFiles: a\n## T999 | pending | Next\nFiles: b'
            (cwd / 'TASKS.md').write_text(manifest)
            record = dict(task='T998', title='Interrupted', allowed=['a', 'PROGRESS.md'],
                          base='head', manifest=manifest, repairs=0, complete=False)
            (state / 'active-run.json').write_text(json.dumps(record))
            args = SimpleNamespace(agent='omp', dry_run=False, bootstrap=False, max_tasks=2)
            completed = []
            def execute(_args, worktree, _logs, task, recovery=False):
                if recovery:
                    self.assertEqual(task['task'], 'T998')
                    (worktree / 'TASKS.md').write_text(manifest.replace('T998 | pending', 'T998 | done'))
                return task['task']
            with patch.object(improve, 'STATE', state), patch.object(improve.shutil, 'which', return_value='/omp'), patch.object(improve, 'git', return_value=improve.BRANCH), patch.object(improve, 'changed', side_effect=[{'a'}, set()]), patch.object(improve, 'ownership'), patch.object(improve, 'save_record'), patch.object(improve, 'execute_task', side_effect=execute) as worker:
                improve.session_work(args, state, completed)
                self.assertEqual(completed, ['T998', 'T999'])
                self.assertEqual(worker.call_count, 2)

    def test_wrong_branch_blocks_before_agent(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            (state / 'worktree').mkdir()
            args = SimpleNamespace(agent='omp', dry_run=False)
            with patch.object(improve, 'STATE', state), patch.object(improve.shutil, 'which', return_value='/omp'), patch.object(improve, 'git', return_value='user-branch'), patch.object(improve, 'execute_task') as worker:
                with self.assertRaisesRegex(RuntimeError, 'Wrong branch'):
                    improve.session_work(args, state, [])
                worker.assert_not_called()
