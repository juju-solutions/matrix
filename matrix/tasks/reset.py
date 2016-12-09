

async def reset(context, rule, task, event=None):
    rule.log.info("Resetting model")
    await context.juju_model.reset()
    rule.log.info("Reset COMPLETE")
    return True
