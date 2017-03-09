import asyncio
import logging
import yaml

from pathlib import Path

from .actions import Actions
from matrix.model import TestFailure
from .plan import generate_plan, validate_plan
from .selectors import Selectors


log = logging.getLogger("chaos")
DEFAULT_PLAN_NAME = "chaos_plan.yaml"


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
    """Raised when no objects were found for a chaos."""


async def perform_action(action, model, rule):
    """Perform a chaos action.

    This is a destructive operation, both for the supplied action and for the
    model.

    :param actions: A list of actions from a chaos plan.
    :param model: A Juju model to apply the actions to.
    :param rule: A model.Rule, typically used for logging.  Passed on to
        the chaos action.
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
    rule.log.info("Creating CHAOS {}: {}".format(actionf.__name__, objects))

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


async def chaos(context, rule, task, event=None):
    """
    Perform a set of actions against a model, with a mind toward causing
    trouble.

    The set of actions is defined by a plan, which is either passed in at
    config time, or generated on the fly.

    We write the last plan to be run out to a YAML file.

    """
    rule.log.info("Starting chaos")

    model = context.juju_model
    config = context.config

    chaos_file = None
    if task.args.get('plan'):
        # If the user specifies {bundle}/some/path in matrix config,
        # replace 'bundle' with the path to the bundle.
        chaos_file = Path(task.args['plan'].format(bundle=config.path))
    elif config.chaos_plan:
        chaos_file = Path(config.chaos_plan)

    if chaos_file:
        with chaos_file.open('r') as f:
            chaos_plan = validate_plan(yaml.load(f))
        rule.log.info("loaded chaos plan from {}".format(chaos_file))
    else:
        chaos_plan = await generate_plan(
            rule,
            model,
            num=int(config.chaos_num))
        chaos_plan = validate_plan(chaos_plan)

        if config.output_dir:
            chaos_output = Path(config.output_dir,
                                 config.chaos_output.format(
                                     model_name=model.info.name))
        else:
            chaos_output = Path(config.chaos_output.format(
                model_name=model.info.name))
        rule.log.info("Writing chaos plan to {}".format(chaos_output))
        with chaos_output.open('w') as output_file:
            output_file.write(yaml.dump(chaos_plan))

    # Execute chaos plan. We perform destructive operations here!
    for action in chaos_plan['actions']:
        try:
            fname, errors = await perform_action(action, model, rule)
        except NoObjects as e:
            # If we get an empty set of objects back, just skip this action.
            rule.log.error(e)
            continue

        if errors and task.gating:
            raise TestFailure(
                task, "Exceptions were raised during chaos run.")

        context.bus.dispatch(
            origin="chaos",
            payload={'action': fname, **action},
            kind="chaos.activate"
        )
        await asyncio.sleep(2, loop=context.loop)

    rule.log.info("Chaos is waiting for model to settle.")
    await model.block_until(model.all_units_idle)

    rule.log.info("Finished chaos")

    return True
