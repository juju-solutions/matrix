import subprocess
from pathlib import Path

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
        with Path(self.tmpdir, self.artifacts[0]).open() as matrix_log:
            infra_failure = False
            msg = "WebSocket connection is closed: code = 1000, no reason."
            for line in matrix_log.readlines():
                if msg in line:
                    infra_failure = True
                    break

        self.assertTrue(infra_failure)
