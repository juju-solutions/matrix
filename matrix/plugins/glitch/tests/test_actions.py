import unittest

from glitch.actions import action, ACTION_MAP

class TestAction(unittest.TestCase):
    def setUp(self):
        self.old_actions = ACTION_MAP

    def tearDown(self):
        ACTION_MAP = self.old_actions

    def test_define(self):
        self.assertFalse('faux_action' in ACTION_MAP.keys())

        @action
        def faux_action(model, *args, **kwargs):
            pass

        self.assertTrue('faux_action' in ACTION_MAP.keys())

if __name__ == '__main__':
    unittest.main()
