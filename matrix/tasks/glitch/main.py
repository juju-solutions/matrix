import asyncio
import logging
import yaml

from pathlib import Path

from .actions import Actions
from matrix.model import TestFailure
from .plan import generate_plan, validate_plan
from .selectors import Selectors


log = logging.getLogger("glitch")
DEFAULT_PLAN_NAME = "glitch_plan.yaml"


def default_resolver(model, kind, name):
    if kind not in ["application", "unit", "model", "controller", "relation"]:
        return None
    entities = getattr(model, kind + "s")
    obj = entities[name]
    return obj


async def select(rule, model, selectors, objects=None,
                 resolver=default_resolver):
    if not selectors:
        if objects is None:
            raise ValueError('No valid objects specified by selectors')
        return objects

    # if there are string names being passed (from a serialized plan for
    # example) we must resolve them relative to the current model. This is
    # pluggable using a resolver object which takes a model,
    cur = None
    args = [rule, model]
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

        cur = await m(*args, **data)
        if len(cur) < 1:  # If we get an empty list ...
            return cur  # ... return it, and skip the rest.
        args = [rule, model, cur]
    return cur


class NoObjects(Exception):
    """Raised when no objects were found for a glitch."""


async def perform_action(action, model, rule):
    """Perform a glitch action.

    This is a destructive operation, both for the supplied action and for the
    model.

    :param actions: A list of actions from a glitch plan.
    :param model: A Juju model to apply the actions to.
    :param rule: A model.Rule, typically used for logging.  Passed on to
        the glitch action.
    :raises: NoObjects if no objects were found to perform the action on.
    :return: A tuple of (fname, bool), where fname is the name of the action's
        function, and bool is True if errors were encountered, False otherwise.
    """
    actionf = Actions[action.pop('action')]['func']
    fname = actionf.__name__
    selectors = action.pop('selectors')
    # Find a set of units to act upon
    objects = await select(rule, model, selectors)
    if not objects:
        raise NoObjects("Could not run {}. No objects for selectors {}".format(
                        actionf.__name__, selectors))

    # Run the specified action on those units
    rule.log.info("GLITCHING {}: {}".format(actionf.__name__, objects))

    try:
        await asyncio.wait_for(actionf(rule, model, objects, **action), 30)
    except asyncio.TimeoutError:
        rule.log.error("Timeout running {}".format(actionf.__name__))
        return fname, True
    except Exception as e:
        rule.log.exception(
            "Exception while running {}: {} {}.".format(
                actionf.__name__, type(e), e))
        return fname, True
    else:
        return fname, False


async def glitch(context, rule, task, event=None):
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

    glitch_file = None
    if task.args.get('plan'):
        # If the user specifies {bundle}/some/path in matrix config,
        # replace 'bundle' with the path to the bundle.
        glitch_file = Path(task.args['plan'].format(bundle=config.path))
    elif config.glitch_plan:
        glitch_file = Path(config.glitch_plan)

    if glitch_file:
        with glitch_file.open('r') as f:
            glitch_plan = validate_plan(yaml.load(f))
        rule.log.info("loaded glitch plan from {}".format(glitch_file))
    else:
        glitch_plan = await generate_plan(
            rule,
            model,
            num=int(config.glitch_num))
        glitch_plan = validate_plan(glitch_plan)

        if config.output_dir:
            glitch_output = Path(config.output_dir,
                                 config.glitch_output.format(
                                     model_name=model.info.name))
        else:
            glitch_output = Path(config.glitch_output.format(
                model_name=model.info.name))
        rule.log.info("Writing glitch plan to {}".format(glitch_output))
        with glitch_output.open('w') as output_file:
            output_file.write(yaml.dump(glitch_plan))

    # Execute glitch plan. We perform destructive operations here!
    for action in glitch_plan['actions']:
        try:
            fname, errors = await perform_action(action, model, rule)
        except NoObjects as e:
            # If we get an empty set of objects back, just skip this action.
            rule.log.error(e)
            continue

        if errors and task.gating:
            raise TestFailure(
                task, "Exceptions were raised during glitch run.")

        context.bus.dispatch(
            origin="glitch",
            payload={'action': fname, **action},
            kind="glitch.activate"
        )
        await asyncio.sleep(2, loop=context.loop)

    rule.log.info("Glitch is waiting for model to settle.")
    await model.block_until(model.all_units_idle)

    rule.log.info("Finished glitch")

    return True
