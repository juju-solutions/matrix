import asyncio


async def reset(context, rule, task, event=None):
    rule.log.info("Resetting model")
    await asyncio.wait([app.destroy() for app in context.apps])
    await context.juju_model.block_until(
        lambda: all(app.dead for app in context.apps)
    )
    context.apps.clear()
    rule.log.info("Reset COMPLETE")
    return True
