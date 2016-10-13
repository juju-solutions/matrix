import random

from .selectors import Selectors


class InvalidPlan(Exception):
    pass


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

        selectors = [s['selector'] for s in action['selectors']]
        if not Selectors.valid_chain(selectors):
            raise InvalidPlan('Action has invalid chain of selectors: {}'.format(selectors))

    return plan


def generate_plan(model, num, action_map):
    '''
    Generate a test plan. The resultant plan, if written out to a
    .yaml file, would look something like the following:

    glitch:
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

    apps = model.applications
    print("model.applications: {}".format(apps))
    units = []
    for a in apps.values():
        units += a.units

    for i in range(0, num):
        unit = random.choice(units)
        action = random.choice([v for v in action_map.values()])
        # Setup implicit selectors
        selectors = [
            {'selector': 'units', 'applications': [unit.application]},
            # TODO: Call is-leader via run, I think
            #{'selector': 'leader', 'application': unit.is_leader()},
            {'selector': 'one'},
        ]

        plan['actions'].append(
            {
                'action': action.__name__,
                # TODO: get some good default args for each action
                'selectors': selectors
            }

        )
    return plan
