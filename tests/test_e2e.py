import asyncio
import mock
import os
import pytest

from matrix import utils
import matrix.tasks.end_to_end as end_to_end


def test_py(loop, resolve_dotpath):
    context = mock.Mock()
    rule = mock.Mock()
    task = mock.Mock()
    e2e = resolve_dotpath()

    assert loop.run_until_complete(end_to_end(context, rule, task))
    e2e.assert_called_once_with(context.juju_model, rule.log)
    assert rule.log.error.called
    assert 'Early termination' in rule.log.error.call_args[0][0]


def test_sh(loop, resolve_dotpath):
    context = mock.MagicMock()
    rule = mock.Mock()
    task = mock.Mock()
    resolve_dotpath.side_effect = AttributeError
    filename = context.config.path / '' / ''
    filename.__str__ = lambda s: '/bin/echo'
    filename.exists.return_value = True
    context.juju_model.info.name = 'model'

    assert loop.run_until_complete(end_to_end(context, rule, task))
    assert rule.log.info.call_count == 2
    assert rule.log.info.call_args[0][0] == 'model'
    assert rule.log.error.called
    assert 'Early termination' in rule.log.error.call_args[0][0]


def test_skip(loop, resolve_dotpath, access):
    context = mock.MagicMock()
    rule = mock.Mock()
    task = mock.Mock()
    resolve_dotpath.side_effect = AttributeError
    filename = context.config.path / '' / ''
    filename.__str__ = lambda s: 'filename'

    # doesn't exist
    filename.exists.return_value = False
    access.return_value = False
    assert loop.run_until_complete(end_to_end(context, rule, task))
    assert rule.log.info.called
    assert 'SKIPPING' in rule.log.info.call_args[0][0]

    # exists, but not executable
    filename.exists.return_value = True
    access.return_value = False
    rule.log.info.reset_mock()
    assert loop.run_until_complete(end_to_end(context, rule, task))
    assert rule.log.info.called
    assert 'SKIPPING' in rule.log.info.call_args[0][0]


# ------------- Fixtures -------------

async def async_noop(*args, **kwargs):
    pass


@pytest.fixture
def loop():
    default_loop = asyncio.get_event_loop()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    asyncio.set_event_loop(default_loop)


@pytest.fixture
def resolve_dotpath():
    patcher = mock.patch.object(utils, 'resolve_dotpath')
    rdp = patcher.start()
    rdp().side_effect = async_noop
    yield rdp
    patcher.stop()


@pytest.fixture
def access():
    patcher = mock.patch.object(os, 'access')
    access = patcher.start()
    yield access
    patcher.stop()
