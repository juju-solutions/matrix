from datetime import timedelta, datetime

from .glitch import glitch  # noqa


async def deploy(context, rule, action, event=None):
    rule.log.info("Deploying %s", action.args['entity'])
    context.apps.extend(await context.juju_model.deploy(action.args['entity']))
    rule.log.info("Deploy COMPLETE")
    return True


async def health(context, rule, action, event=None):
    if not context.apps:
        # this shouldn't happen, because the health rule has
        # an "after: deploy", but that doesn't seem to be honored
        return
    stable_period = timedelta(seconds=30)
    errored_units = []
    busy_units = []
    for app in context.apps:
        for unit in app.units:
            now = datetime.utcnow()
            agent_status_duration = now - unit.agent_status_since
            agent_busy = agent_status_duration < stable_period
            workload_status_duration = now - unit.workload_status_since
            workload_busy = workload_status_duration < stable_period
            unit_busy = agent_busy or workload_busy

            if unit.workload_status == 'error':
                errored_units.append(unit)
            elif (unit_busy or
                  unit.agent_status != 'idle' or
                  unit.workload_status not in ('active', 'unknown')):
                busy_units.append(unit)

    if errored_units:
        result = 'unhealthy'
    elif busy_units:
        result = 'busy'
    else:
        result = 'healthy'

    context.set_state('deployment', result)
    rule.log.info("Health check: %s", result)
