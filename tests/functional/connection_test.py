import subprocess

from .harness import Harness


class TestConnection(Harness):
    '''
    Verify that our methods of handling a broken connection do what we
    expect them to do.

    '''
    def setUp(self):
        super(TestConnection, self).setUp()
        self.cmd.append("-D")  # Skip default tests
        self.artifacts = ['matrix.log']  # No chaos plan

    def test_broken_connection(self):
        test = 'tests/test_broken_connection.matrix'
        proc = subprocess.run(self.cmd + [test], check=False)
        self.assertEqual(proc.returncode, 1)
        self.check_artifacts(1)  # log
