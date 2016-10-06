import asyncio
import random

async def chaos(context, rule, action):
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
    for i in range(5):
        kind = random.choice(chaos_options)
        rule.log.debug("CHAOS: %s %s", kind, i)
        context.bus.dispatch(
                origin="chaos",
                payload=kind,
                kind="chaos.activate"
                )
        await asyncio.sleep(2, loop=context.loop)
    rule.log.info("Stop the chaos")
    return True
