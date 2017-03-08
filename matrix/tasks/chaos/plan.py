import random

from .selectors import Selectors
from .actions import Actions
from .tags import SUBORDINATE_OK


class InvalidPlan(Exception):
    pass


class InvalidModel(Exception):
    pass


async def _fetch_machine(rule, model, tags):
    machines = [m for m in model.machines.values()]
    if not machines:
        raise InvalidModel("No machines in the model.")

    machine = random.choice(machines)

    selectors = [
        {'selector': 'machines'},
        {'selector': 'one'},
    ]
    return selectors


async def _fetch_unit(rule, model, tags):
    units = [u for u in model.units.values()]
    if not units:
        raise InvalidModel("No units in the model.")

    if SUBORDINATE_OK not in tags:
        units = [u for u in units if not u.subordinate]

    unit = random.choice(units)

    leadership = await unit.is_leader_from_status()

    selectors = [
        {'selector': 'units', 'application': unit.application},
        {'selector': 'leader', 'value': leadership},
        {'selector': 'one'},
    ]
    return selectors


async def _fetch_application(rule, model, tags):
    apps = [a for a in model.applications.keys()]

    if SUBORDINATE_OK not in tags:
        apps = [a for a in apps if not model.applications[a].subordinate]

    if not apps:
        raise InvalidModel("No apps in the model.")
    app = random.choice(apps)

    selectors = [
        {'selector': 'applications', 'application': app},
    ]
    return selectors


async def fetch(rule, object_type, model, tags=None):
    if object_type == 'machine':
        return await _fetch_machine(rule, model, tags)
    if object_type == 'unit':
        return await _fetch_unit(rule, model, tags)
    if object_type == 'application':
        return await _fetch_application(rule, model, tags)


def validate_plan(plan):
    '''
    Validate our plan. Raise an InvalidPlan exception with a helpful
    error message if we run into anything that is not valid.

    '''
    if not 'actions' in plan:
        raise InvalidPlan('Plan missing "actions" key: {}'.format(plan))

    for action in plan['actions']:
        if not 'action' in action:
            raise InvalidPlan('Action missing "action" key: {}'.format(action))

        if not action.get('selectors'):
            continue

    return plan


async def generate_plan(rule, model, num):
    '''
    Generate a test plan. The resultant plan, if written out to a
    .yaml file, would look something like the following:

    chaos:
      format: v1
      actions:
        - action: reboot
          inflight: 1
          interval: 5m
          selectors:
            - selector: units
              application: zookeeper
            - selector: leader
              value: False
            - selector: count
              value: 1

    In an autogenerate plan, we simply select a random unit, pair it
    with a random action, and record the values for the set of
    'implicit selectors'; which selectors are implicit is simply
    defined in the code below -- we assume that the selectors that we
    list exist elsewhere in the codebase.

    '''
    plan = {'actions': []}

    for i in range(0, num):
        action = random.choice([a for a in Actions])
        obj_type = Actions[action]['type']
        tags = Actions[action]['tags']

        selectors = await fetch(rule, obj_type, model, tags)

        plan['actions'].append({'action': action, 'selectors': selectors})

    return plan
