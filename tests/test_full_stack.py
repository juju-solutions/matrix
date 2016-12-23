from pathlib import Path
import pytest
import unittest

from matrix.main import main


class TestFullStack(unittest.TestCase):
    def test_stack(self):
        controller = pytest.config.getoption('--controller')
        if not controller:
            raise unittest.SkipTest()
        bundle = Path(__file__).parent / 'basic_bundle'
        main(['-c', controller, '-p', str(bundle), '-s', 'raw'])
