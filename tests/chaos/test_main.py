import asyncio
import logging
from tempfile import NamedTemporaryFile
import unittest
from unittest.mock import patch
import yaml

from juju.model import Model
from juju.delta import ApplicationDelta, UnitDelta

from matrix import model
from matrix.tasks.chaos import actions
from matrix.bus import Bus
from matrix.tasks.chaos.main import (
    chaos,
    NoObjects,
    perform_action,
    )


def kill_juju_agent(application='foo'):
    return {
        'action': 'kill_juju_agent',
        'selectors': [{
            'selector': 'units',
            'application': application,
            }],
        }


def make_test_model(foo_unit=True, foo_status='idle'):
    juju_model = Model()
    state = juju_model.state
    state.apply_delta(ApplicationDelta(
        ('application', 'type2', {'name': 'foo'})))
    if foo_unit:
        state.apply_delta(UnitDelta(('unit', 'type1', {
            'name': 'steve',
            'application': 'foo',
            # Add some status to fake out chaos's "wait 'til the
            # cloud is idle" check.
            'agent-status': {'current': foo_status}
            })))
    return juju_model


class TestPerformAction(unittest.TestCase):

    def setUp(self):
        self.rule = model.Rule(model.Task(command='chaos',
                                          args={'path': None}))
        self.rule.log.setLevel(logging.CRITICAL)
        self.loop = asyncio.get_event_loop()

    def test_perform_action_happy_path(self):
        juju_model = make_test_model()
        self.assertEqual(
            ('kill_juju_agent', False),
            self.loop.run_until_complete(
                perform_action(kill_juju_agent(), juju_model, self.rule)))

    def test_perform_action_no_objects(self):
        juju_model = make_test_model(foo_unit=False)
        with self.assertRaisesRegex(
                NoObjects,
                r"Could not run kill_juju_agent. No objects for selectors"):
            self.loop.run_until_complete(perform_action(
                kill_juju_agent(), juju_model, self.rule))

    def test_perform_action_error(self):
        juju_model = make_test_model()
        async def kill_raise(a, b, c):
            raise Exception
        with patch.dict(actions.Actions, {'kill_juju_agent': {
                'func': kill_raise,
                }}):
            self.assertEqual(
                ('kill_raise', True),
                self.loop.run_until_complete(
                    perform_action(kill_juju_agent(), juju_model, self.rule)))

    def test_perform_action_timeout_error(self):
        juju_model = make_test_model()
        async def kill_raise(a, b, c):
            raise asyncio.TimeoutError()
        with patch.dict(actions.Actions, {'kill_juju_agent': {
                'func': kill_raise,
                }}):
            self.assertEqual(
                ('kill_raise', True),
                self.loop.run_until_complete(
                    perform_action(kill_juju_agent(), juju_model, self.rule)))


class TestChaos(unittest.TestCase):

    def test_chaos(self):
        task = model.Task(command='chaos', args={'path': None})
        rule = model.Rule(task)
        loop = asyncio.get_event_loop()
        bus = Bus(loop=loop)
        suite = []

        class config:
            path = None

        context = model.Context(loop, bus, suite, config, None)

        juju_model = make_test_model()
        context.juju_model = juju_model

        plan = {'actions': [kill_juju_agent()]}

        with NamedTemporaryFile() as plan_file:
            yaml.safe_dump(plan, plan_file, encoding='utf8')
            task.args['plan'] = plan_file.name
            loop.run_until_complete(chaos(context, rule, task, None))


if __name__ == '__main__':
    unittest.main()
