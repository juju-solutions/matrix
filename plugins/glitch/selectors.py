import random
from functools import wraps


class Selectors(object):
    selector_map = {}

    @classmethod
    def decorator(cls, requires, returns=None):
        '''
        Add a function to our map of selectors. Each function 'requires' a
        set of objects of some type, and 'returns' a set of objects of
        some type. You must pass in at least the type that the
        function 'requires'; we assume that the returned type is the
        same if it is not specified.

        If a selector 'requires' objects of type 'none', we assume
        that the selector is a 'starter' -- that it is the first thing
        in a list of selectors, and it will get the initial set of
        objects.

        A selector might also require 'any', in which case, it accepts
        any type of object. If a selector requires 'any', and returns
        objects matching whatever type of object it was passed, you
        can specify this by passing 'same' to 'returns'.

        '''
        if returns is None:
            returns = requires

        def add_to_selectors(func):
            cls.selector_map[func.__name__] = {
                'func': func,
                'requires': requires,
                'returns': returns,
                'starter': requires == 'none'
            }
            return func
        return add_to_selectors

    @classmethod
    def func(cls, selector):
        '''Given a selector name, return an executable function.'''

        return cls.selector_map[selector]['func']

    @classmethod
    def valid_chain(cls, selectors):
        '''Verify that a set of selectors chains together.'''

        def chain(selectors, returns=None, requires=None):
            '''
            Given a list of selector objects, check successive pairs to verify
            that their 'requires' and 'returns' values match.

            '''
            if returns is None and requires is None:
                # Initialize our recursive function.

                if len(selectors) < 1:
                    # An empty chain is not valid.
                    return False

                if not selectors[0]['starter'] or selectors[0]['returns'] == 'same':
                    # We have to start with a starter, and it doesn't
                    # make sense for it to return 'same'
                    return False

                if len(selectors) == 1:
                    # A chain comprised of only a starter is valid.
                    return True

                return chain(
                    selectors,
                    returns=selectors[0]['returns'],
                    requires=selectors[1]['requires']
                )

            if requires != 'any' and requires != returns:
                return False

            if len(selectors) <= 2:
                # Exit.
                return True

            # Update requires and returns. If something returns
            # 'same', then keep the type from the last pass.
            requires = selectors[2]['requires']
            if selectors[1]['returns'] != 'same':
                returns = selectors[1]['returns']

            return chain(selectors[1:], returns=returns, requires=requires)

        return chain([cls.selector_map[s] for s in selectors])


# Name our decorator something nicer
selector = Selectors.decorator

#
# Define your selectors here
#

@selector(requires='none', returns='units')
def units(model, nounits, applications=None):
    '''
    Return units that are part of the specified application(s).

    If no application is specified, simply return all units.

    '''
    if applications is None:
        apps = model.applications
    else:
        apps = [model.applications[a] for a in applications]

    units = []
    for a in apps:
        units += a.units()

    return units


@selector(requires='units')
def leader(model, units, value=True):
    '''
    Return just the units that are, or are not the leader, depending
    on whether 'value' is truthy or falsy.

    '''
    return [u for u in units if u.is_leader is value]


@selector(requires='units')
def agent_status(model, units, string=None):
    '''
    Return units with an agent status matching a string.

    '''
    # TODO: regex matching?
    return [u for u in units if string == u.agent_status]


@selector(requires='units')
def workload_status(model, units, string=None):
    '''
    Return units with a workload status matching a string.

    '''
    # TODO: regex matching?
    return [u for u in units if string == u.workload_status]


@selector(requires='units')
def health(units):
    '''
    Placeholder for eventual health check selector.

    '''
    raise Exception("Not yet implemented.")


@selector(requires='any', returns='same')
def one(model, objects):
    '''
    Return just one of a set of units.

    The theory is that, whenever we call this, any of the units will
    do, so we select a unit at random, to avoid biases introduced by
    just selecting the first unit in the list.

    '''
    return [random.select(objects)]
