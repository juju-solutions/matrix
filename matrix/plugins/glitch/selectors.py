import functools
import logging
import random
from typing import List, Any

import enforce
from juju.model import Model
from juju.application import Application
from juju.unit import Unit

from matrix.utils import Singleton


_marker = object()
log = logging.getLogger("glitch")


class _Selectors(dict, metaclass=Singleton):
    def decorate(self, f):
        wrapper = enforce.runtime_validation(f)
        wrapper = functools.update_wrapper(wrapper, f)
        name = f.__name__
        self[f.__qualname__] = wrapper
        if name in self:
            # There is a conflict in short name
            log.warn("selector %s already registered %s vs %s",
                     name, f.__qualname__,
                     self[name].__qualname__)
        else:
            self[name] = wrapper
        return wrapper

Selectors = _Selectors()
selector = Selectors.decorate


@selector
def units(model: Model, application: Application=None) -> List[Unit]:
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
def leader(model: Model, units: List[Unit], value=True) -> List[Unit]:
    """
    Return just the units that are, or are not the leader, depending
    on whether 'value' is truthy or falsy.

    TODO: fix this to actually check for leadership.

    """
    return [u for u in units if u.is_leader is value]


@selector
def agent_status(model: Model, units: List[Unit], expect):
    '''
    Return units with an agent status matching a string.

    '''
    # TODO: regex matching?
    return [u for u in units if expect == u.agent_status]


@selector
def workload_status(model: Model, units: List[Unit], expect=None):
    """
    Return units with a workload status matching a string.

    """
    # TODO: regex matching?
    return [u for u in units if expect == u.workload_status]


@selector
def health(units: List[Unit]):
    """"
    Placeholder for eventual health check selector.

    """
    raise NotImplementedError()


@selector
def one(model: Model, objects: List[Any]) -> List[Any]:
    """
    Return just one of a set of units.

    The theory is that, whenever we call this, any of the units will
    do, so we select a unit at rmandom, to avoid biases introduced by
    just selecting the first unit in the list.

    """
    return [random.choice(objects)]
