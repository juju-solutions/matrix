import asyncio
import os
from matrix import utils


async def end_to_end(context, rule, task, event=None):
    """
    Attempt to discover an end_to_end load generator within
    the bundle, and run in during the test case.

    The load generator can be either:

        * An async function in the file ``tests/end_to_end.py``
          called ``end_to_end``.  This function should accept
          two arguments, a ``Model`` instance from libjuju, and
          a logger instance to optionally send messages to.

        * An executable file ``tests/end_to_end`` which is called
          with the model name as a single argument.

    In either case, the load generator should run until terminated
    from the outside, and continue to perform actions that put some
    reasonable amount of load to exercise the model as a whole.  If
    the model is not functioning as expected, the generator can output
    an appropriate message on the logger's ``error` method or on the
    process' stderr, and terminate.
    """
    try:
        e2e = utils.resolve_dotpath('tests.end_to_end.end_to_end')
        rule.log.info("Running bundle-provided end_to_end function")
        await e2e(context.juju_model, rule.log)
        rule.log.error('Early termination; model may not be healthy')
    except (ImportError, AttributeError):
        e2e_sh = context.config.path / 'tests' / 'end_to_end'
        if e2e_sh.exists() and os.access(str(e2e_sh), os.X_OK):
            rule.log.info("Running bundle-provided end_to_end executable")
            proc = await asyncio.create_subprocess_exec(
                str(e2e_sh), context.juju_model.info.name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
            await asyncio.gather(
                e2e_output(proc.stdout, rule.log.info),
                e2e_output(proc.stderr, rule.log.error))
            rule.log.error('Early termination; model may not be healthy')
        else:
            rule.log.info("SKIPPING: No end-to-end provided by bundle")
    return True


async def e2e_output(stream, log_func):
    while True:
        line = await stream.readline()
        if not line:
            return
        log_func(line.decode('utf8').strip())
