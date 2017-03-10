import functools
import logging
import random
from typing import List, Any

import enforce
from juju.model import Model
from juju.application import Application
from juju.unit import Unit

from matrix.model import Rule
from matrix.utils import Singleton


_marker = object()
log = logging.getLogger("chaos")


class SelectError(Exception):
    pass


class _Selectors(dict, metaclass=Singleton):
    def decorate(self, f):
        wrapper = enforce.runtime_validation(f)
        wrapper = functools.update_wrapper(wrapper, f)
        name = f.__name__
        self[f.__qualname__] = wrapper
        if name in self:
            # There is a conflict in short name
            log.debug("selector %s already registered %s vs %s",
                      name, f.__qualname__,
                      self[name].__qualname__)
        else:
            self[name] = wrapper
        return wrapper


Selectors = _Selectors()
selector = Selectors.decorate


@selector
async def units(rule: Rule, model: Model, application: Application=None):
    """
    Return units that are part of the specified application(s).

    If no application is specified, simply return all units.

    """
    if application is None:
        apps = model.applications
    else:
        apps = [application]

    units = []
    for a in apps:
        units.extend(a.units)

    return units


@selector
async def machines(rule: Rule, model: Model):
    machines = [m for m in model.machines.values()]
    return machines


@selector
async def applications(rule: Rule, model: Model,
                       application: Application=None):
    if application is None:
        return [a for a in model.applications.values()]
    else:
        # All the work is done for us in spinning up the application
        # object. Just return it.
        return [application]


@selector
async def leader(rule: Rule, model: Model, units: List[Unit], value=True):
    """
    Return just the units that are, or are not the leader, depending
    on whether 'value' is truthy or falsy.

    """
    passed = []

    for unit in units:
        if await unit.is_leader_from_status():
            passed.append(unit)

    # Return our list of leaders or not leaders. If value is True,
    # this list should be of length one, but this selector does not
    # take responsibility for checking for that.
    return passed


@selector
async def agent_status(rule: Rule, model: Model, units: List[Unit], expect):
    '''
    Return units with an agent status matching a string.

    '''
    return [u for u in units if expect == u.agent_status]


@selector
async def workload_status(rule: Rule, model: Model, units: List[Unit],
                          expect=None):
    """
    Return units with a workload status matching a string.

    """
    return [u for u in units if expect == u.workload_status]


@selector
async def health(units: List[Unit]):
    """"
    Placeholder for eventual health check selector.

    """
    raise NotImplementedError()


@selector
async def one(rule: Rule, model: Model, objects: List[Any]):
    """
    Return just one of a set of units.

    The theory is that, whenever we call this, any of the units will
    do, so we select a unit at rmandom, to avoid biases introduced by
    just selecting the first unit in the list.

    """
    return [random.choice(objects)]
