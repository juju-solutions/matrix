import asyncio
import functools
import logging
import time
import yaml

from .selectors import Selectors
from .actions import Actions
from .plan import generate_plan, validate_plan


log = logging.getLogger("glitch")
DEFAULT_PLAN_NAME = "glitch_plan.yaml"


def default_resolver(model, kind, name):
    if kind not in ["application", "unit", "model", "controller", "relation"]:
        return None
    entities = getattr(model, kind + "s")
    obj = entities[name]
    return obj


def select(model, selectors, objects=None, resolver=default_resolver):
    if not selectors:
        if objects is None:
            raise ValueError('No valid objects specified by selectors')
        return objects

    # if there are string names being passed (from a serialized plan for
    # example) we must resolve them relative to the current model. This is
    # pluggable using a resolver object which takes a model,
    cur = None
    args = [model]
    # This can raise many an exception
    for selector in selectors:
        data = selector.copy()
        m = Selectors.get(data.pop('selector'))
        for k, v in data.items():
            if isinstance(v, str):
                # attempt resolution
                o = resolver(model, k, v)
                if o is not None:
                    data[k] = o

        cur = m(*args, **data)
        args = [model, cur]
    return cur


async def glitch(context, rule, action, event=None):
    """
    Perform a set of actions against a model, with a mind toward causing
    trouble.

    The set of actions is defined by a plan, which is either passed in at
    config time, or generated on the fly.

    We write the last plan to be run out to a YAML file.

    """
    rule.log.info("Starting glitch")

    model = context.juju_model
    config = context.config

    if config.glitch_plan:
        with open(config.glitch_plan, 'r') as f:
            glitch_plan = validate_plan(yaml.load(f))
        rule.log.info("loaded glitch plan from {}".format(config.glitch_plan))
    else:
        glitch_plan = generate_plan(model, num=int(config.glitch_num))
        glitch_plan = validate_plan(glitch_plan)

        rule.log.info("Writing glitch plan to {}".format(config.glitch_output))
        with open(config.glitch_output, 'w') as output_file:
            output_file.write(yaml.dump(glitch_plan))

    # Execute glitch plan. We perform destructive operations here!
    for action in glitch_plan['actions']:
        actionf = Actions[action.pop('action')]['func']
        selectors = action.pop('selectors')
        # Find a set of units to act upon
        objects = select(model, selectors)

        # Run the specified action on those units
        rule.log.debug("GLITCHING {}: {}".format(actionf.__name__, action))

        # TODO: better handle the case where we no longer have objects
        # to select, due to too many of them being destroyed (most
        # relevant for small bundles)
        await actionf(rule, model, objects, **action)
        context.bus.dispatch(
            origin="glitch",
            payload={'action': actionf.__name__, **action},
            kind="glitch.activate"
        )
        await asyncio.sleep(2, loop=context.loop)

    rule.log.info("Finished glitch")
    return True
