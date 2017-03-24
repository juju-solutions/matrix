from distutils.spawn import find_executable
import subprocess
import unittest

from .harness import Harness


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
            '-r', 'conjure-up',
            '-D',
        ]

    def test_basic_spell(self):
        subprocess.run(self.cmd + ['tests/test_deploy.matrix'], timeout=1000)
        self.check_artifacts(1)  # matrix.log

    if not find_executable("conjure-up"):
        test_basic_spell = unittest.skip("Conjure up not installed")(
            test_basic_spell)
