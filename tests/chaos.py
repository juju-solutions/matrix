import asyncio
import random
from os import urandom

async def chaos(context, rule):
    chaos_options = [
      "Reboot Unit",
      "Remove Unit",
      "Creating Netsplit",
      "Scaling up",
      "Scaling down",
      "Killing Juju Agents",
      "Deposing leader",
      "Sever controller connection",
      "Flipping Tables",
      "All the hippos go berserk"
    ]
    rule.log.info("Starting chaos")

    # Check to see if the plugin's config specifies a specific list of
    # operations to perform.
    operations = rule.config.chaos_ops # TODO: is this the right way
                                       # to get the config for a rule?
    if not operations:
        # No operations specified; generate a list. Use a random seed
        # if no seed is specified in the config.
        seed = rule.config.chaos_seed or int.from_bytes(
            urandom(4), byteorder='little')
        rule.log.info('Running chaos with seed {}'.format(seed))
        num_ops = rule.config.num_ops
        operations = [random.choice(chaos_options) for i in range(num_ops)]

    for op in operations:
        rule.log.debug("CHAOS: %s %s", kind, i)
        context.bus.dispatch(
                origin="chaos",
                payload=op,
                kind="chaos.activate"
                )
        await asyncio.sleep(2, loop=context.loop)
    rule.log.info("Stop the chaos")
    return True
