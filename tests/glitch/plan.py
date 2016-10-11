import random


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
            {'selector': 'count', 'value': 1},
        ]

        plan['actions'].append(
            {
                'action': action,
                # TODO: get some good default args for each action
                'selectors': selectors
            }

        )
    return plan
