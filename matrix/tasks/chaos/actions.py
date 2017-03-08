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

from .tags import SUBORDINATE_OK

log = logging.getLogger("chaos")


class _Actions(dict, metaclass=Singleton):
    """
    Interface for registering actions, translating text strings into
    action functions, and performing automagic around our action
    functions.

    """
    def decorate(self, *args):
        """
        Register an action. Possibly add some 'tags' (strings) that code
        further down the pipeline can use to decide what to do with
        this action. For example, we can include a SUBORDINATE_OK tag
        to tell the plan generator that it is okay to run this action
        against a subordinate charm.

        """
        if callable(args[0]):
            return self._action(*args)

        # else tags are specified
        def wrapped_action(func):
            return self._action(func, tags=args)
        return wrapped_action

    def _action(self, func, tags=None):
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
action = Actions.decorate


#
# Define your actions here
#
@action(SUBORDINATE_OK)
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


#@action
# Disabling for now, as it is semi-duplicated by remove_unit,
# and it's harder to avoid removing the last unit of an application
# with the info available to a Machine object.
async def destroy_machine(rule: Rule, model: Model, machine: Machine, force: bool=True):
    """Remove a machine."""

    await machine.destroy(force=force)


@action
async def remove_unit(rule: Rule, model: Model, unit: Unit):
    """Destroy a unit."""

    application = unit.application
    if len(model.applications[application].units) < 2:
        rule.log.warning(
            "Skipping remove unit for {}, as it is the last unit in {}".format(
                unit, application))
        return

    await unit.remove()


@action
async def add_unit(rule: Rule, model: Model, application: Application,
                   count: int=1, to: str=None):
    """Scale up an application by adding a unit (or units) to it."""

    await application.add_unit(count=count, to=to)


@action(SUBORDINATE_OK)
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
