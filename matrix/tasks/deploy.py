from matrix.utils import execute_process
from matrix.model import TestFailure

import yaml


async def libjuju(context, rule):
    """
    Deploy a bundle or charm via libjuju.

    """
    await context.juju_model.deploy(str(context.config.path))


async def get_controller_name(controller_id, log):
    if controller_id.startswith('controller-'):
        controller_id = controller_id[11:]

    success, controllers, _ = await execute_process(
        ["juju", "list-controllers", "--format", "yaml"],
        log
    )
    if not success:
        raise TestFailure("Unable to get controllers.")

    controllers = yaml.safe_load(controllers.decode('utf8'))
    controllers = controllers.get('controllers')

    if not controllers:
        raise TestFailure("Unable to get controllers.")

    for controller in controllers:
        if controllers[controller]['uuid'] == controller_id:
            return controller

    raise TestFailure(
        "Unable to find controller {}".format(controller_id))


async def conjureup(context, rule):
    """
    Assuming that we've been passed a spell in place of a bundle,
    deploy it via conjure-up.

    """
    cloud = await context.juju_controller.get_cloud()
    controller_name = await get_controller_name(
        context.juju_controller.connection.info['controller-tag'],
        rule.log
    )
    cmd = [
        'conjure-up',
        str(context.config.path),
        cloud,
        controller_name,
        context.juju_model.info.name
    ]

    success, _, err = await execute_process(cmd, rule.log)
    if not success:
        raise TestFailure("Unable to execute conjure-up: {}".format(err))


DEPLOYERS = {
    'python-libjuju': libjuju,
    'libjuju': libjuju,
    'pythonlibjuju': libjuju,
    'conjure-up': conjureup,
    'conjureup': conjureup
}


async def deploy(context, rule, task, event=None):
    rule.log.info(
        "Deploying %s via %s", context.config.path, context.config.deployer)
    try:
        deployer = DEPLOYERS[context.config.deployer]
    except KeyError:
        raise TestFailure(
            "Could not find deployer '{}'".format(context.config.deployer))
    await deployer(context, rule)
    rule.log.info("Deploy COMPLETE")
    return True
