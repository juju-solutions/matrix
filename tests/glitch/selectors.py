import random

#
# Scaffolding
#

SELECTOR_MAP = {}  # TODO: add some custom error handling for missing keys

def selector(func):
    '''
    Add a function to our dict of selectors

    '''
    SELECTOR_MAP[func.__name__] = func
    return func

#
# Define your selectors here
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



