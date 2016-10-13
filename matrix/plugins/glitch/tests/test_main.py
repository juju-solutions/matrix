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

    def set_model(self):
        async def _set_model():
            from juju.model import Model
            model = Model()
            await model.connect_current()
            self.model = model

        self.loop.run_until_complete(_set_model())

    def test_glitch(self):
        self.action.args = {}
        self.assertTrue(self.context.model)

        @asyncio.coroutine
        async def _test_glitch():
            await glitch(self.context, self.rule, self.action)
        self.loop.run_until_complete(_test_glitch())


if __name__ == '__main__':
    unittest.main()
