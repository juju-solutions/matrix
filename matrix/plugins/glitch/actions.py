import asyncio
import logging
from typing import Any
from functools import wraps

import enforce
from juju.model import Model
from juju.unit import Unit

from matrix.utils import Singleton

log = logging.getLogger("glitch")


class _Actions(dict, metaclass=Singleton):
    """
    Interface for registering actions, translating text strings into
    action functions, and performing automagic around our action
    functions.

    """
    def decorate(self, func):
        """
        Register an action. Return a function that accepts a set of objects,
        and iterates over that set, running the registered action on each
        object in that set.

        """
        @enforce.runtime_validation
        @wraps(func)
        async def wrapped(model, objects, **kwargs):
            for obj in objects:
                await func(model, obj, **kwargs)
        self[func.__name__] = wrapped
        return wrapped

# Public singleton
Actions = _Actions()
action = Actions.decorate


#
# Define your actions here
#
@action
async def reboot(model: Model, unit: Unit):
    """
    Given a set of units, send a reboot command to all of them.

    """
    await unit.run('sudo reboot')


async def sleep(model: Model=None, obj: Any=None, seconds=2):
    """Sleep for the given number of seconds."""
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
