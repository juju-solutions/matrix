import random

from .selectors import Selectors
from .actions import Actions

class InvalidPlan(Exception):
    pass

class InvalidModel(Exception):
    pass


_MODEL_OPS = {
    'machine': {
        'fetch': lambda model: [m for m in model.machines.values()],
        'selectors': lambda m: [
            {'selector': 'machines'}, {'selector': 'one'}],
    },
    'unit': {
        'fetch': lambda model: [u for u in model.units.values()],
        'selectors': lambda u: [
            {'selector': 'units', 'application': u.application},
            # TODO: handle leadership
            {'selector': 'one'}
        ]
    },
    'application': {
        'fetch': lambda model: [a for a in model.applications.values()],
        'selectors': lambda a: [
            {'selector': 'applications'},
            {'selector': 'one'}
        ]
    }
}


def _fetch_objects(object_type, model):
    try:
        func = _MODEL_OPS[object_type]['fetch']
    except KeyError:
        raise InvalidPlan("Could not fetch objects of {}".format(object_type))
    objects = func(model)
    if not objects:
        raise InvalidModel("No objects to test in the current model")
    return objects


def _implicit_selectors(object_type, obj):
    try:
        func = _MODEL_OPS[object_type]['selectors']
    except KeyError:
        raise InvalidPlan("Could not get implicit selectors for {}".format(object_type))
    return func(obj)


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


def generate_plan(model, num):
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

    for i in range(0, num):
        action = random.choice([a for a in Actions])

        sig = [arg for arg in Actions[action]['args'] if arg in _MODEL_OPS.keys()]
        if len(sig) < 1:
            raise InvalidPlan("Empty signature for action {}".format(action))
        if len(sig) > 1:
            raise InvalidPlan(
                "Found more than one value to use as "
                "signature for action {} ({}).".format(action, sig))
        sig = sig[0]

        objects = _fetch_objects(sig, model)
        obj = random.choice(objects)
        selectors = _implicit_selectors(sig, obj)

        plan['actions'].append({'action': action, 'selectors': selectors})

    return plan
