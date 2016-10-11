import asyncio
import functools
import petname
import random
import yaml

DEFAULT_OUTPUT = '/tmp/last_glitch_plan.yaml'
SELECTORS = {}
ACTIONS = {}

def selector(func):
    '''
    Add a function to our dict of selectors

    '''
    SELECTORS[func.__name__] = func
    return func


def action(func):
    '''
    Add a function to our dict of actions

    '''
    ACTIONS[func.__name__] = func
    return func


#
# Selectors
#
@selector
def units(model, units=None, applications=None):
    '''
    Return units that are part of the specified application(s).

    If no application is specified, simply return all units.

    '''
    # Handle the case where we already have a set of units
    if units:
        if applications:
            return [u for u in units if u.application in applications]
        # noop
        return units

    # Handle the case where we do not yet have a set of units.
    if applications is None:
        apps = model.applications
    else:
        apps = [model.applications[a] for a in applications]

    units = []
    for a in apps:
        units += a.units()

    return units


@selector
def leader(model, units=None, value=True):
    '''
    Return just the units that are, or are not the leader, depending
    on whether 'value' is truthy or falsy.

    '''
    units = units or model.units

    return [u for u in units if u.is_leader is value]


@selector
def agent_status(model, units=None, string=None):
    '''
    Return units with an agent status matching a string.

    '''
    units = units or model.units

    # TODO: regex matching?
    return [u for u in units if string == u.agent_status]


@selector
def workload_status(model, units=None, string=None):
    '''
    Return units with a workload status matching a string.

    '''

    units = units or model.units

    # TODO: regex matching?
    return [u for u in units if string == u.workload_status]


@selector
def health(units=None):
    '''
    Placeholder for eventual health check selector.

    '''
    raise Exception("Not yet implemented.")


@selector
def one(model, units=None):
    '''
    Return just one of a set of units.

    The theory is that, whenever we call this, any of the units will
    do, so we select a unit at random, to avoid biases introduced by
    just selecting the first unit in the list.

    '''
    units = units or model.units

    return [random.select(units)]


#
# Actions
#
@action
def reboot(units):
    '''
    Given a set of units, send a reboot command to all of them.

    '''
    for unit in units:
        # TODO: replace 'run_action' with the actual method in libjuju.
        unit.run_action('reboot')


@action
def sleep(seconds=2):
    '''Sleep for the given number of seconds.'''
    await asyncio.sleep(seconds)


# TODO: implement these actions:
#    Reboot Unit
#    Remove Unit
#    Creating Netsplit
#    Scaling up
#    Scaling down
#    Killing Juju Agents
#    Deposing leader
#    Sever controller connection
#    Flipping Tables
#    All the hippos go berserk

#
# Glitch
#

def generate_plan(model, num):
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
        action = random.select(ACTION)
        selectors = [
            # Setup implicit selectors
            {'selector': 'units', 'application': unit.application},
            {'selector': 'leader': 'application': unit.is_leader()},
            {'selector': 'count', 'value': 1},
        ]

        plan['actions'].append(
            'action': action,
            # TODO: get some good default args for each action
            'selectors': selectors

        )
    return plan


async def glitch(context, rule, action):
    '''


    '''
    rule.log.info("Starting glitch")

    glitch_output = []
    output_filename = DEFAULT_OUTPUT

    glitch_plan = action.args.get('glitch_plan') or generate_plan(
        context.model, num=action.args.get('glitch_num', 5))
    rule.log.info("Writing glitch plan to {}".format(output_file))
    with open(output_filename, 'w') as output_file:
        output_file.write(yaml.dump(glitch_plan))
    
    # Execute glitch plan. We perform destructive operations here!
    for action in glitch_plan:
        selectors = action.pop('selectors')
        actionf = ACTIONS[action.pop('action')]

        # Find a set of units to act upon
        units = None
        for selector in selectors:
            selectf = SELECTORS[selector.pop['selector']]
            units = selectf(context.model, **selector)

        if units is None:
            raise Exception('No valid units specified by selectors.')

        # Run the specified action on those units
        rule.log.debug("GLITCHING {}: {}".format(actionf.__name__, action))
        context.bus.dispatch(
            origin="glitch",
            payload=functools.partial(actionf, **action),
            kind="glitch.activate"
        )
        await asyncio.sleep(2, loop=context.loop)
    rule.log.info("Stop the glitch")
    return True
