async def deploy(context, rule, action, event=None):
    rule.log.info("Deploying %s", action.args['entity'])
    await context.juju_model.deploy(action.args['entity'])
    rule.log.info("Deploy COMPLETE")
    return True
