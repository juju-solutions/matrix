import asyncio
import random
from os import urandom


async def chaos(context, rule, action, event=None):
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
    operations = action.args.get('operations')
    if not operations:
        # No operations specified; generate a list. Use a random seed
        # if no seed is specified in the config.
        seed = 0 if action.args.get("deterministic", True) else (
            int.from_bytes(urandom(4), byteorder="little"))
        rule.log.debug('Running chaos with seed {}'.format(seed))
        # XXX: look at choosing number and types of ops based on models
        # ex: we can identify SPoF by looking but can those units recover
        # at all?
        # XXX: we are also missing the notion of which services or units
        # these ops apply to, which may be critical to reproducibility
        num_ops = action.args.get("num_ops", 5)
        operations = [random.choice(chaos_options) for i in range(num_ops)]

    for i, op in enumerate(operations):
        rule.log.debug("CHAOS: %s %s", op, i)
        context.bus.dispatch(
            origin="chaos",
            payload=op,
            kind="chaos.activate"
        )
        await asyncio.sleep(2, loop=context.loop)
    rule.log.info("Stop the chaos")
    return True
