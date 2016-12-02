import asyncio
import inspect
import logging
from typing import Any
from functools import wraps

import enforce
from juju.model import Model
from juju.unit import Unit
from juju.machine import Machine
from juju.application import Application
from matrix.model import Rule

from matrix.utils import Singleton

log = logging.getLogger("glitch")


class _Actions(dict, metaclass=Singleton):
    """
    Interface for registering actions, translating text strings into
    action functions, and performing automagic around our action
    functions.

    """
    def tagged_action(self, *tags):
        def _tagged_action(func):
            return self.action(func, tags=tags)
        return _tagged_action

    def action(self, func, tags=None):
        """
        Register an action. Return a function that accepts a set of objects,
        and iterates over that set, running the registered action on each
        object in that set.

        """

        @wraps(func)
        async def wrapped(rule, model, objects, **kwargs):
            for obj in objects:
                await enforce.runtime_validation(func(
                    rule, model, obj, **kwargs))
        signature = inspect.signature(func)
        self[func.__name__] = {
            'func': wrapped,
            'type': [p for p in signature.parameters.keys()][2],
            'tags': tags or []
        }
        return wrapped


# Public singleton
Actions = _Actions()
action = Actions.action
tagged_action = Actions.tagged_action


#
# Define your actions here
#
@tagged_action('subordinate_okay')
async def reboot(rule: Rule, model: Model, unit: Unit):
    """
    Given a set of units, send a reboot command to all of them.

    """
    rule.log.debug("rebooting {}".format(unit))
    await unit.run('sudo reboot')


#@action
async def sleep(rule: Rule, model: Model=None, obj: Any=None, seconds=2):
    """Sleep for the given number of seconds."""

    await asyncio.sleep(seconds)


@action
async def destroy_machine(rule: Rule, model: Model, machine: Machine, force: bool=True):
    """Remove a machine."""

    await machine.destroy(force=force)


@action
async def remove_unit(rule: Rule, model: Model, unit: Unit):
    """Destroy a unit."""

    await unit.remove()


@action
async def add_unit(rule: Rule, model: Model, application: Application,
                   count: int=1, to: str=None):
    """Scale up an application by adding a unit (or units) to it."""

    await application.add_unit(count=count, to=to)


@tagged_action('subordinate_okay')
async def kill_juju_agent(rule: Rule, model: Model, unit: Unit):
    """Kill the juju agent on a machine."""

    try:
        await unit.run('sudo pkill jujud')
    except AttributeError:
        # We kill the juju agent, so we will get an Exception back
        # from unit.run.
        pass


# TODO: implement these actions:
#    Creating Netsplit
#    Sever controller connection
#    Flipping Tables
#    All the hippos go berserk
#    Shut down networking daemon/kill a network interface
