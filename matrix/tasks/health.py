from datetime import timedelta, datetime, timezone
from matrix.model import TestFailure


async def health(context, rule, task, event=None):

    # Don't gate by default
    task.gating = task.args.get('gating', False)

    if not (context.juju_model and context.juju_model.applications):
        return True
    stable_period = timedelta(seconds=task.args.get('stability_period', 30))
    errored_apps = []
    busy_apps = []
    errored_units = []
    busy_units = []
    settling_units = []
    for app in context.juju_model.applications.values():
        if app.dead:
            continue
        if app.status == 'error':
            errored_apps.append(app)
        elif app.status not in ('active', 'unknown', ''):
            busy_apps.append(app)
        for unit in app.units:
            now = datetime.now(timezone.utc)
            agent_status_duration = now - unit.agent_status_since
            agent_busy = agent_status_duration < stable_period
            workload_status_duration = now - unit.workload_status_since
            workload_busy = workload_status_duration < stable_period
            unit_busy = agent_busy or workload_busy
            agent_idle = unit.agent_status == 'idle'
            workload_ready = unit.workload_status in ('active', 'unknown')
            workload_error = unit.workload_status == 'error'
            agent_error = unit.agent_status in ('error', 'failed')

            if workload_error or agent_error:
                errored_units.append(unit)
            elif workload_ready and agent_idle and unit_busy:
                settling_units.append(unit)
            elif not workload_ready or not agent_idle or unit_busy:
                busy_units.append(unit)

    if errored_apps or errored_units:
        result = 'unhealthy'
    elif (busy_apps or busy_units) and \
            context.states.get('health.status') != 'healthy':
        result = 'busy'
    elif settling_units and \
            context.states.get('health.status') != 'healthy':
        result = 'settling'
    else:
        result = 'healthy'

    context.set_state('health.status', result)
    if result == 'unhealthy':
        _log = rule.log.error
    else:
        _log = rule.log.info
    _log("Health check: %s", result)

    if result == 'unhealthy' and task.gating:
        rule.log.error("Raising TestFailure due to unhealthy status")
        raise TestFailure(task, 'Health state was unhealthy')

    return True
