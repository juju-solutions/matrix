import os


async def crashdump(context, rule, task, event=None):
    '''
    Dump the logs from the running model.

    Will result in two files in the current working dir:
        matrix.log.gz
        juju-crashdump-<somehash>.tar.gz


    TODO: give the operator some control over where these things get
    dumped (requires wiring up the log-name option for matrix, and
    adding hooks in juju-crashdump to allow one to write dumps with
    custom names, to custom directories.)

    '''
    rule.log.info("Running crash dump")
    rule.log.warning(
        "Crashdump specified, but skipping juju-crashdump due to gh issue #59. "
        "Will still save off matrix log."
    )
    # Run juju-crashdump
    #cmd = [
    #    'juju-crashdump',
    #    '-m',
    #    context.juju_model.info.name,
    #]
    #result = await task.execute_process(context, cmd, rule, env=os.environ)
    #rule.log.info("Crashdump result: {}".format(result))

    # Zip up the matrix logs
    cmd = [
        'gzip',
        'matrix.log',
        '--keep',
        '--force',  # matrix.log.gz is disposable
    ]
    result = await task.execute_process(context, cmd, rule)
    rule.log.info("Crashdump COMPLETE")
    return True
