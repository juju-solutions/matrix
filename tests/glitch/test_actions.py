import unittest

from matrix.tasks.glitch.actions import _Actions


class FauxActions(_Actions):
    pass


class TestAction(unittest.TestCase):
    def setUp(self):
        self.actions = FauxActions()

    def test_define(self):
        self.assertFalse('faux_action' in self.actions)

        @self.actions.action
        def faux_action(model, unit, **kwargs):
            pass

        self.assertTrue('faux_action' in self.actions)

if __name__ == '__main__':
    unittest.main()
