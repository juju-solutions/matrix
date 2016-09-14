import asyncio
import logging
log = logging.getLogger("traffic")

async def test_traffic(context, rule):
    log.info("Start Traffic")
    for i in range(6):
        log.debug("TRAFFIC...")
        await asyncio.sleep(1, loop=context.loop)
    log.info("Stop Traffic")
