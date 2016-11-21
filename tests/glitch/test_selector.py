import unittest

from matrix.tasks.glitch.selectors import selector, Selectors

from enforce.exceptions import RuntimeTypeError


class TestSelectors(unittest.TestCase):
    def test_decorator(self):
        self.assertFalse('faux_select' in Selectors)

        @selector
        def faux_select(model, *args, **kwargs):
            pass

        self.assertTrue('faux_select' in Selectors)

        self.assertEqual(Selectors['faux_select'], faux_select)

    def test_valid_chain(self):

        @selector
        def foo_start() -> int:
            return 1

        @selector
        def foo_one(val: int) -> int:
            return val

        @selector
        def foo_two(val: str) -> int:
            return int(val)

        # Valid chain
        foo_one(foo_start())
        with self.assertRaises(RuntimeTypeError):
            foo_two(foo_start())

if __name__ == '__main__':
    unittest.main()
