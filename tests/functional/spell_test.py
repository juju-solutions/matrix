import subprocess
import unittest
from distutils.spawn import find_executable
from pathlib import Path

from .harness import Harness


@unittest.skipIf(not find_executable("conjure-up"), 'Test requires conjure-up')
class TestBasicSpell(Harness):
    '''
    Verify that we can run the default matrix suite on the basic
    spell, deploying via conjure-up, in reasonable time.

    '''
    def setUp(self):
        super(TestBasicSpell, self).setUp()
        self.artifacts = ['matrix.log', 'chaos_plan*.yaml']

        self.cmd = [
            'matrix',
            '-s', 'raw',
            '-p', 'tests/basic-spell',
            '-d', self.tmpdir,
            '-D',
        ]

    def test_basic_spell(self):
        subprocess.run(self.cmd + ['tests/test_deploy.matrix'], timeout=1000)
        self.check_artifacts(1)  # matrix.log
        with Path(self.tmpdir, self.artifacts[0]).open() as matrix_log:
            deployed_with_conjure = False
            for line in matrix_log.readlines():
                if "Deploying tests/basic-spell via conjure-up" in line:
                    deployed_with_conjure = True
                    break

        self.assertTrue(deployed_with_conjure)
