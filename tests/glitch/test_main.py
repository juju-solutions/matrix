import asyncio
import mock
import unittest
from juju.model import Model

import enforce

from matrix.plugins.glitch.main import glitch


class TestGlitch(unittest.TestCase):

    def setUp(self):
        enforce.config(reset=True)
        self.loop = asyncio.get_event_loop()
        self.context = mock.Mock()
        self.rule = mock.Mock()
        self.rule.log.debug = print
        self.rule.log.info = print
        self.action = mock.Mock()
        self.model = None

        self.set_model()
        self.context.juju_model = self.model
        self.context.loop = self.loop

    def set_model(self):
        '''
        Setup self.model.

        '''
        async def _set_model():
            model = Model()
            await model.connect_current()
            self.model = model

        self.loop.run_until_complete(_set_model())

    def test_glitch(self):
        '''
        Verify that our main "glitch" routine executes smoothly.

        '''
        self.action.args = {}
        self.assertTrue(self.context.model)

        self.loop.run_until_complete(glitch(
            self.context, self.rule, self.action))


if __name__ == '__main__':
    unittest.main()
