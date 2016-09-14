import asyncio
import logging
log = logging.getLogger("deploy")

# example plugins
async def deploy(context, rule):
    # XXX: this is a testing example and will be (re)moved
    log.info("Start Deploy")
    await asyncio.sleep(1.5, loop=context.loop)
    log.info("Deploy DONE")
    rule.complete = True
