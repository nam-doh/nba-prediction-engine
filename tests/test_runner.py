import fcntl
import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts.improve import FATAL, run, scope, tasks


class RunnerTests(unittest.TestCase):
    def test_queue(self):
        self.assertEqual(tasks('## T001 | pending | Guard\nFiles: a, b')[0][2], {'a', 'b'})
        self.assertEqual(tasks('## T001 | done | Guard\nFiles: a'), [])

    def test_fatal(self):
        for message in ('HTTP 401', 'usage limit reached', 'insufficient_quota',
                        'authentication failed', 'rate limit exceeded'):
            self.assertTrue(FATAL.search(message))

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
