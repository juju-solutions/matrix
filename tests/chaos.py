import asyncio
import logging
import random
log = logging.getLogger("chaos")

async def chaos(context, rule):
    chaos_options = [
      "Reboot Unit",
      "Remove Unit",
      "Creating Netsplit",
      "Scaling up",
      "Scaling down",
      "Killing Juju Agents",
      "Sever controller connection",
      "Flipping Tables",
      "All the hippos go berserk"
    ]
    log.info("Starting chaos")
    for i in range(5):
        kind = random.choice(chaos_options)
        log.debug("CHAOS: %s", kind)
        await asyncio.sleep(2, loop=context.loop)
    log.info("Stop the chaos")
    rule.complete = True


