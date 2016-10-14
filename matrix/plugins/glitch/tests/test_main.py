import asyncio
import mock
import unittest
from juju.model import Model

from glitch.main import glitch

class TestGlitch(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.context = mock.Mock()
        self.rule = mock.Mock()
        self.action = mock.Mock()
        self.model = None

        self.set_model()
        self.context.model = self.model
        self.context.loop = self.loop

        self.context.bus.dispatch = self.dispatch

    def dispatch(self, origin, payload, kind):
        '''
        Quick 'n dirty dispatching function.

        TODO: Refactor to better handle exceptions in the dispatched
        function.

        '''
        async def _dispatch():
            await payload()

        self.loop.create_task(_dispatch())

    def set_model(self):
        '''
        Setup self.model.

        '''
        async def _set_model():
            from juju.model import Model
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

        @asyncio.coroutine
        async def _test_glitch():
            await glitch(self.context, self.rule, self.action)
        self.loop.run_until_complete(_test_glitch())


if __name__ == '__main__':
    unittest.main()
