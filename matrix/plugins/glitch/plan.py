import random

from .selectors import Selectors


class InvalidPlan(Exception):
    pass


def _validate_plan(plan):
    # TODO: flesh this out; possibly use something nicer than assert
    assert 'operations' in plan

    for action in plan['operations']:
        assert 'action' in action
        if not action.get('selectors'):
            continue
        selectors = [s['selector'] for s in action['selectors']]
        assert Selectors.valid_chain(selectors)

    return plan


def validate_plan(plan):
    try:
        plan = _validate_plan(plan)
    except (AssertionError, KeyError) as e:
        # TODO: better messaging/catching for KeyErrors
        raise InvalidPlan('Invalid plan: {}'.format(e))

    return plan


def generate_plan(model, num, action_map):
    '''
    Generate a test plan. The resultant plan, if written out to a
    .yaml file, would look something like the following:

    glitch:
      format: v1
      operations:
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

    apps = model.applications
    units = []
    for a in apps:
        units += a.units()

    for i in range(0, num):
        unit = random.select.unit()
        action = random.select(action_map)['action']
        # Setup implicit selectors
        selectors = [
            {'selector': 'units', 'application': unit.application},
            {'selector': 'leader', 'application': unit.is_leader()},
            {'selector': 'one'},
        ]

        plan['actions'].append(
            {
                'action': action,
                # TODO: get some good default args for each action
                'selectors': selectors
            }

        )
    return plan
