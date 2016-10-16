import asyncio

# example plugins
async def deploy(context, rule, action, event=None):
    rule.log.info("Start Deploy")
    await asyncio.sleep(1.5, loop=context.loop)
    rule.log.info("Deploy DONE")
    return True
