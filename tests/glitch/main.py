import asyncio
import functools
import yaml

from .selectors import SELECTOR_MAP as selector_map
from .actions import ACTION_MAP as action_map

DEFAULT_OUTPUT = '/tmp/last_glitch_plan.yaml'


async def glitch(context, rule, action):
    '''


    '''
    rule.log.info("Starting glitch")

    glitch_output = []
    output_filename = DEFAULT_OUTPUT

    glitch_plan = action.args.get('glitch_plan') or generate_plan(
        context.model,
        num=action.args.get('glitch_num', 5),
        action_map=action_map
    )
    rule.log.info("Writing glitch plan to {}".format(output_file))
    with open(output_filename, 'w') as output_file:
        output_file.write(yaml.dump(glitch_plan))

    # Execute glitch plan. We perform destructive operations here!
    for action in glitch_plan:
        selectors = action.pop('selectors')
        actionf = action_map[action.pop('action')]

        # Find a set of units to act upon
        units = None
        for selector in selectors:
            selectf = selector_map[selector.pop['selector']]
            units = selectf(context.model, **selector)

        if units is None:
            raise Exception('No valid units specified by selectors.')

        # Run the specified action on those units
        rule.log.debug("GLITCHING {}: {}".format(actionf.__name__, action))
        context.bus.dispatch(
            origin="glitch",
            payload=functools.partial(actionf, **action),
            kind="glitch.activate"
        )
        await asyncio.sleep(2, loop=context.loop)
    rule.log.info("Stop the glitch")
    return True
