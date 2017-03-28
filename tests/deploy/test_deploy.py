import mock
import pytest

from pkg_resources import resource_filename

from matrix.tasks.deploy import libjuju
from matrix.model import Context
from matrix import rules


def loader(name):
    return resource_filename(__name__, name)


class FauxModel:
    def __init__(self, mock_deploy):
        self.mock_deploy = mock_deploy

    async def deploy(self, path):
        self.mock_deploy(path)


@pytest.mark.asyncio
async def test_libjuju(event_loop):
    s = rules.load_suites([loader("../rules.1.yaml")])
    config = mock.MagicMock()
    mock_deploy = mock.Mock()
    config.path = "foo"

    context = Context(
        loop=None, bus=None, config=config, juju_controller=None, suite=s)
    context.juju_model = FauxModel(mock_deploy)

    await libjuju(context, None)

    mock_deploy.assert_called_once_with("foo")
