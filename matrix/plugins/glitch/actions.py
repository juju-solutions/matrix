import asyncio
from functools import wraps


class Actions(object):
    '''
    Interface for registering actions, translating text strings into
    action functions, and performing automagic around our action
    functions.

    '''
    action_map = {}

    @classmethod
    def decorator(cls, func):
        '''
        Register an action with our action _map. Return a function that
        accepts a set of objects, and iterates over that set, running
        the registered action on each object in that set.

        '''
        async def wrapped(model, objects, **kwargs):
            for obj in objects:
                await func(model, obj, **kwargs)
        cls.action_map[func.__name__] = wrapped
        return wrapped

    @classmethod
    def func(cls, action):
        '''
        Given an action name, return a function with that name.

        '''
        return cls.action_map[action]

    @classmethod
    def actions(cls):
        '''Fetch a list of all actions in our action map.'''
        return [a for a in cls.action_map.keys()]

# Give our decorator a better name
action = Actions.decorator

#
# Define your actions here
#
@action
async def reboot(model, unit):
    '''
    Given a set of units, send a reboot command to all of them.

    '''
    await unit.run('sudo reboot')


async def sleep(nomodel, noobj, seconds=2):
    '''Sleep for the given number of seconds.'''
    print("foo")
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
