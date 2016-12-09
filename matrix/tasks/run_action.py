from random import choice


async def run_action(context, rule, task, event=None):
    """
    Matrix rule task to run an action

    Arguments:

    :param application: Required. Name of application to run action against.
    :param unit: Optional. Unit number, "leader", or not set.  Not providing
        this will select a random unit. Providing "leader" will run the action
        on the unit which is the leader.  A number will select the Nth unit
        from the deployment, as ordered by their unit name (nb: the number
        provided may not match with the number in the unit name).
    :param action: Required.  Name of action to run.
    :param params: Optional.  Mapping of action params to values.
    """
    app_name = task.args['application']
    unit_selector = task.args.get('unit')
    action_name = task.args['action']
    params = task.args['params']
    if app_name not in context.juju_model.applications:
        raise ValueError('Application not found: %s', app_name)
    app = context.juju_model.applications[app_name]
    if unit_selector is None:
        unit = choice(app.units)
    elif unit_selector == 'leader':
        for unit in app.units:
            if unit.is_leader:
                break
        else:
            raise ValueError('Application has no leader??')
    elif str.isdecimal(unit_selector):
        unit = sorted(app.units, key=lambda u: u.name)[int(unit_selector)]
    else:
        raise ValueError('Invalid unit selector: %s (must be int or leader)',
                         unit_selector)

    rule.log.info('Running %s on %s', action_name, unit.name)
    action = await unit.run_action(action_name, **params)
    await action.wait()
    context.set_state('run_action.%s' % action_name, action.status)
    return True
