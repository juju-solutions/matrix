import asyncio

async def test_traffic(context, rule, action):
    rule.log.info("Start Traffic")
    try:
        for i in range(16):
            rule.log.debug("TRAFFIC... %s", i)
            await asyncio.sleep(1, loop=context.loop)
    except asyncio.CancelledError:
        pass
    rule.log.info("Stop Traffic")
    return True
