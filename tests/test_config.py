import mock
import unittest

from matrix import main


class TestConfig(unittest.TestCase):

    def test_add_bundle_opts(self):
        """
        _test_add_bundle_opts_

        This test requires that we have a test.yaml in
        tests/basic_bundle/test.yaml, with a model_prefix equal to
        matrixtest.

        """
        options = mock.Mock()
        parser = mock.Mock()
        options.path = 'tests/basic_bundle'
        options.model_prefix = 'matrix'  # default
        parser.get_default.return_value = 'matrix'

        # Verify that we can override a default value
        options = main.add_bundle_opts(options, parser)
        self.assertEqual(options.model_prefix, 'matrixtest')

        # Verify that we can't override a non default value
        options.model_prefix = 'bar'
        options = main.add_bundle_opts(options, parser)
        self.assertEqual(options.model_prefix, 'bar')
