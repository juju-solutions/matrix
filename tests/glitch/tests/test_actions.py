import unittest

from glitch.actions import action, ACTION_MAP

class TestAction(unittest.TestCase):
    def test_define(self):
        self.assertFalse('faux_action' in ACTION_MAP.keys())

        @action
        def faux_action(model, *args, **kwargs):
            pass

        self.assertTrue('faux_action' in ACTION_MAP.keys())

if __name__ == '__main__':
    unittest.main()
