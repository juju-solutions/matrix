import subprocess

from .harness import Harness


class TestGating(Harness):
    '''
    Verify that we exit with an exit code other than 0 when
    appropriate, based on TestFailures or uncaught Exceptions in
    matrix.

    '''
    def setUp(self):
        super(TestGating, self).setUp()
        self.cmd.append("-D")  # Skip default tests
        self.artifacts = ['matrix.log']  # No chaos plan

    def test_gating_test_failure(self):
        test = 'tests/test_gating.matrix'
        proc = subprocess.run(self.cmd + [test], check=False, timeout=60)
        self.assertEqual(proc.returncode, 1)
        self.check_artifacts(1)  # log

    def test_gating_uncaught_exception(self):
        test = 'tests/test_uncaught_exception.matrix'
        proc = subprocess.run(self.cmd + [test], check=False, timeout=60)
        self.assertEqual(proc.returncode, 1)
        self.check_artifacts(1)  # log

    def test_turn_off_gating(self):
        test = 'tests/test_non_gating.matrix'
        proc = subprocess.run(self.cmd + [test], check=False, timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.check_artifacts(1)  # log
