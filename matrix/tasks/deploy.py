

async def deploy(context, rule, task, event=None):
    rule.log.info("Deploying %s", task.args['entity'])
    context.apps.extend(await context.juju_model.deploy(task.args['entity']))
    rule.log.info("Deploy COMPLETE")
    return True
