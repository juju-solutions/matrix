import unittest

from glitch.selectors import selector, SELECTOR_MAP

class TestSelector(unittest.TestCase):
    def test_define(self):
        self.assertFalse('faux_select' in SELECTOR_MAP.keys())

        @selector
        def faux_select(model, *args, **kwargs):
            pass

        self.assertTrue('faux_select' in SELECTOR_MAP.keys())

if __name__ == '__main__':
    unittest.main()
