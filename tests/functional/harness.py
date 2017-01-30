from logging import getLogger
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase


class Harness(TestCase):
    '''
    Testing harness for our functional tests.

    Provides a default command, which will, when passed to subprocess
    unaltered, run the default matrix test on the basic bundle.

    Also provides some facilities that a test can call to check up and
    make sure that we create expected artifacts, like logs,
    crashdumps, and glitch plans.

    '''
    def check_artifacts(self, num=None):
        '''
        Verify that that artifacts that we expect to exist, do.

        Optionally verify the number of artifacts created.

        '''
        artifacts = []
        for a in self.artifacts:
            artifacts += Path(self.tmpdir).glob(a)

        for a in artifacts:
            self.assertTrue(a.exists())

        if num is not None:
            self.assertEqual(len(artifacts), num)

    def setUp(self):
        self.log = getLogger('functional_tests')

        self.tmpdir = mkdtemp()
        self.log.info("Outputting artifacts to {}".format(self.tmpdir))

        self.cmd = [
            'matrix',
            '-s', 'raw',
            '-p', 'tests/basic_bundle',
            '-d', self.tmpdir
        ]
        self.artifacts = []

    def tearDown(self):
        rmtree(self.tmpdir)
