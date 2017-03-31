import unittest
import mock
from pathlib import Path

from matrix import utils


class TestUtils(unittest.TestCase):
    def test_should_gate(self):
        context = mock.Mock()
        task = mock.Mock()

        task.gating = True
        self.assertTrue(utils.should_gate(context, task))

        task.gating = 'ha_only'
        context.config.ha = False
        self.assertFalse(utils.should_gate(context, task))

        task.gating = 'ha_only'
        context.config.ha = True
        self.assertTrue(utils.should_gate(context, task))

        task.gating = False
        self.assertFalse(utils.should_gate(context, task))

    def test_valid_bundle_or_spell(self):
        self.assertTrue(
            utils.valid_bundle_or_spell(Path('tests/basic_bundle')))
        self.assertTrue(
            utils.valid_bundle_or_spell(Path('tests/basic-spell')))
        self.assertFalse(
            utils.valid_bundle_or_spell(Path('tests/bad_bundle')))
        self.assertFalse(
            utils.valid_bundle_or_spell(Path('tests/bad_bundle_file')))
