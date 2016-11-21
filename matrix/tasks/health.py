from datetime import timedelta, datetime


async def health(context, rule, task, event=None):
    stable_period = timedelta(seconds=task.args.get('stability_period', 30))
    errored_apps = []
    busy_apps = []
    errored_units = []
    busy_units = []
    for app in context.apps:
        if app.status == 'error':
            errored_apps.append(app)
        elif app.status not in ('active', 'unknown'):
            busy_apps.append(app)
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

    if errored_apps or errored_units:
        result = 'unhealthy'
    elif (busy_apps or busy_units) and \
            context.states.get('health.status') != 'healthy':
        result = 'busy'
    else:
        result = 'healthy'

    context.set_state('health.status', result)
    rule.log.info("Health check: %s", result)
    return True
