

async def deploy(context, rule, task, event=None):
    rule.log.info("Deploying %s", task.args['entity'])
    curr_apps = {app.name for app in context.apps}
    new_apps = await context.juju_model.deploy(task.args['entity'])
    new_apps = list(filter(lambda a: a.name not in curr_apps, new_apps))
    context.apps.extend(new_apps)
    rule.log.info("Deploy COMPLETE")
    return True
