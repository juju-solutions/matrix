import unittest

from glitch.selectors import selector, Selectors

class TestSelectors(unittest.TestCase):
    def test_decorator(self):
        self.assertFalse('faux_select' in Selectors.selector_map.keys())

        @selector('units')
        def faux_select(model, *args, **kwargs):
            pass

        self.assertTrue('faux_select' in Selectors.selector_map.keys())

        self.assertEqual(Selectors.func('faux_select'), faux_select)

    def test_valid_chain(self):

        @selector('none', 'units')
        def foo_start(*args, **kwargs):
            pass

        @selector('units')
        def foo_one(*args, **kwargs):
            pass

        @selector('any', 'same')
        def foo_two(*args, **kwargs):
            pass

        # Valid chain
        self.assertTrue(Selectors.valid_chain(['foo_start', 'foo_one', 'foo_two']))
        self.assertTrue(Selectors.valid_chain(['foo_start', 'foo_one']))
        self.assertTrue(Selectors.valid_chain(['foo_start']))

        # Doesn't start with a starter
        self.assertFalse(Selectors.valid_chain(['foo_one', 'foo_start', 'foo_two']))
        self.assertFalse(Selectors.valid_chain(['foo_one', 'foo_start']))
        self.assertFalse(Selectors.valid_chain(['foo_two']))

        # TODO: define more selectors and make more tests of more iteractions


if __name__ == '__main__':
    unittest.main()
