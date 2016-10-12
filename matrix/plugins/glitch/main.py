import asyncio
import functools
import yaml

from .selectors import Selectors
from .actions import ACTION_MAP as action_map
from .plan import generate_plan, validate_plan

DEFAULT_OUTPUT = '/tmp/last_glitch_plan.yaml'

def select_units(model, selectors, units=None):
    if len(selectors) == 0:
        if units is None:
            # TODO: custom Exception class
            raise Exception('No valid units specified by selectors')
        return units

    selector = selectors.pop(0)
    selectf = Selectors.func[selector.pop['selector']]
    units = selectf(model, units, **selector)

    return select_units(model, selectors, units)


async def glitch(context, rule, action):
    '''
    Peform a set of actions against a model, with a mind toward
    causing trouble.

    The set of actions is defined by a plan, which is either passed in
    at config time, or generated on the fly.

    We write the last plan to be run out to a yaml file.

    '''
    rule.log.info("Starting glitch")

    glitch_output = []
    output_filename = DEFAULT_OUTPUT  # TODO: make configurable.

    glitch_plan = validate_plan(
        action.args.get('glitch_plan') or generate_plan(
            context.model,
            num=action.args.get('glitch_num', 5),
            action_map=action_map))

    rule.log.info("Writing glitch plan to {}".format(output_file))
    with open(output_filename, 'w') as output_file:
        output_file.write(yaml.dump(glitch_plan))

    # Execute glitch plan. We perform destructive operations here!
    for action in glitch_plan:
        actionf = action_map[action.pop('action')]
        selectors = action.pop('selectors')

        # Find a set of units to act upon
        units = select_units(model, selectors)

        # Run the specified action on those units
        rule.log.debug("GLITCHING {}: {}".format(actionf.__name__, action))
        context.bus.dispatch(
            origin="glitch",
            payload=functools.partial(actionf, **action),
            kind="glitch.activate"
        )
        await asyncio.sleep(2, loop=context.loop)

    rule.log.info("Finished glitch")
    return True
