import unittest

from glitch.actions import Actions, action

class TestAction(unittest.TestCase):
    def test_define(self):
        self.assertFalse('faux_action' in Actions.action_map.keys())

        @action
        def faux_action(model, unit, **kwargs):
            pass

        self.assertTrue('faux_action' in Actions.action_map.keys())

if __name__ == '__main__':
    unittest.main()
