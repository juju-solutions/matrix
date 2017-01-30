import subprocess
from pathlib import Path
import os

from .harness import Harness


class TestEnv(Harness):
    '''
    Verify that we can set config via env variables.

    '''
    def setUp(self):
        super(TestEnv, self).setUp()

        self.cmd = [
            'matrix',
            '-s', 'raw',
            '-p', 'tests/basic_bundle',
            '-D'
        ]
        os.environ['MATRIX_OUTPUT_DIR'] = self.tmpdir
        self.artifacts = ['matrix.log']

    def tearDown(self):
        os.unsetenv('MATRIX_OUTPUT_DIR')

    def test_set_env(self):
        test = 'tests/test_non_gating.matrix'  # Lightweight test
        proc = subprocess.run(self.cmd + [test], check=False, timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.check_artifacts(1)  # log
