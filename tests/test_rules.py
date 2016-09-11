from pathlib import Path
from pkg_resources import resource_filename

import pytest

from matrix import rules
from matrix.utils import O


def loader(name):
    return Path(resource_filename(__name__, name))


def test_parser():
    s = rules.load_suite(loader("rules.1.yaml").open())
    # Suite should have one test with 3 rules
    assert len(s) == 1
    assert len(s[0]) == 3


def test_rule_conditions():
    context = O(states={"deploy.done": True})
    s = rules.load_suite(loader("rules.1.yaml").open())
    t = s[0]
    assert t[0].match(context) is True
    assert t[1].match(context) is True
    assert t[2].match(context) is False

    context.states['chaos.done'] = True
    context.states['test_traffic.done'] = True
    context.states['test_traffic.running'] = True
    assert t[0].match(context) is True
    assert t[1].match(context) is False
    assert t[2].match(context) is True

    assert t[0].has("until") is False
    assert t[1].has("until") is True
    assert t[2].has("until") is False
    assert t[0].has("while") is False
    assert t[1].has("while") is False
    assert t[2].has("while") is True


@pytest.mark.asyncio
async def test_ruleengine_loader(event_loop):
    event_loop.set_debug(True)
    context = rules.Context(loop=event_loop, suite=[])
    r = rules.RuleEngine()
    r.load_suite(loader("rules.1.yaml").open(), context)
    await r.run_once(context, context.tests[0])
    await asyncio.gather(*context.tasks.values())
