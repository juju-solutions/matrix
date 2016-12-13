

async def deploy(context, rule, task, event=None):
    rule.log.info("Deploying %s", context.config.path)
    await context.juju_model.deploy(str(context.config.path))
    rule.log.info("Deploy COMPLETE")
    return True
