import unittest
import mock

from matrix import utils


class TestUtils(unittest.TestCase):
    def test_should_gate(self):
        context = mock.Mock()
        task = mock.Mock()

        task.gating = True
        self.assertTrue(utils.should_gate(context, task))

        task.gating = 'ha_only'
        context.ha = False
        self.assertFalse(utils.should_gate(context, task))

        task.gating = 'ha_only'
        context.ha = True
        self.assertTrue(utils.should_gate(context, task))

        task.gating = False
        self.assertFalse(utils.should_gate(context, task))
