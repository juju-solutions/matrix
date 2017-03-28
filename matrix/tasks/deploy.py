import yaml
from distutils.spawn import find_executable
from pathlib import Path

from juju import client

from matrix.model import InfraFailure
from matrix.utils import execute_process


async def libjuju(context, rule):
    """
    Deploy a bundle or charm via libjuju.

    """
    await context.juju_model.deploy(str(context.config.path))


async def get_controller_name(controller_id, context, log):
    if controller_id.startswith('controller-'):
        controller_id = controller_id[11:]

    controllers = client.connection.JujuData().controllers()

    if not controllers:
        raise InfraFailure("Unable to get controllers.")

    for controller in controllers:
        if controllers[controller]['uuid'] == controller_id:
            return controller

    raise InfraFailure(
        "Unable to find controller {}".format(controller_id))


def is_spell(bundle):
    """
    Determine whether a bundle is a conjure-up friendly spell or not.

    Currently, something is a spell if it has a metadata.yaml file
    with a 'friendly-name' key in it.

    """
    metadata_yaml = Path(bundle, 'metadata.yaml')
    if not metadata_yaml.exists():
        return False

    with metadata_yaml.open('r') as metadata:
        return yaml.safe_load(metadata).get('friendly-name')


async def conjureup(context, rule):
    """
    Assuming that we've been passed a spell in place of a bundle,
    deploy it via conjure-up.

    """
    cloud = await context.juju_controller.get_cloud()
    controller_name = await get_controller_name(
        context.juju_controller.connection.info['controller-tag'],
        context,
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
        raise InfraFailure("Unable to execute conjure-up: {}".format(err))


async def deploy(context, rule, task, event=None):
    """
    Determine what method to use to deploy the bundle specified in
    context.config.path, and deploy it via the appropriate method.

    This routine assumes that the bundle path points to a local
    directory; matrix currently does not have support for deploying
    remotely stored bundles.

    """
    if find_executable('conjure-up') and is_spell(context.config.path):
        rule.log.info("Deploying %s via conjure-up", context.config.path)
        await conjureup(context, rule)
    else:
        rule.log.info("Deploying %s via python-libjuju", context.config.path)
        await libjuju(context, rule)

    rule.log.info("Deploy COMPLETE")
    return True
