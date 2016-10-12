import asyncio


#
# Scaffolding
#
# TODO: refactor to match what we did with selectors.
#

ACTION_MAP = {}


def action(func):
    '''
    Add a function to our dict of actions

    '''
    ACTION_MAP[func.__name__] = func
    return func


#
# Define your actions here
#
@action
async def reboot(units):
    '''
    Given a set of units, send a reboot command to all of them.

    '''
    for unit in units:
        # TODO: replace 'run_action' with the actual method in libjuju.
        unit.run_action('reboot')


async def sleep(seconds=2):
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
