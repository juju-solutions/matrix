from pkg_resources import resource_filename

from matrix import model
from matrix import rules


def loader(name):
    return resource_filename(__name__, name)


def test_parser():
    s = rules.load_suites([loader("rules.1.yaml")])
    # Suite should have one test with 3 rules
    assert len(s) == 3
    assert len(s[0].rules) == 5
    assert s[0].rules[0].task.args['entity'] == 'cs:bundle/wiki-simple'
    assert s[0].rules[-1].task.command == 'matrix.tasks.reset'

    # test merge with overrides and adds
    s = rules.load_suites([loader("rules.1.yaml"), loader("rules.2.yaml")])
    assert len(s) == 4
    assert len(s[0].rules) == 1
    assert s[0].rules[0].task.command == 'tests.chaos.chaos'
    assert s[-1].rules[0].task.command == 'tests.health'


def test_rule_conditions():
    s = rules.load_suites([loader("rules.1.yaml")])
    context = model.Context(
            loop=None, bus=None, config=None, juju_model=None,
            suite=s)
    context.states.update({"deploy": "complete"})
    t = s[0].rules
    assert t[0].has("until") is False
    assert t[1].has("until") is True
    assert t[2].has("until") is False
    assert t[0].has("while") is False
    assert t[1].has("while") is False
    assert t[2].has("while") is True

    assert t[0].match(context) is True
    assert t[1].match(context) is False
    assert t[2].match(context) is False

    context.states['chaos'] = "complete"
    context.states['test_traffic'] = "running"
    context.states['health.status'] = 'healthy'
    assert t[0].match(context) is True
    # The until condition here is already met
    # thus the rule won't match
    assert t[1].match(context) is False
    assert t[2].match(context) is True
    # The until condition here is already met
    # thus the rule won't match
    assert t[3].match(context) is False
