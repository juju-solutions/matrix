import asyncio
from matrix.model import TestFailure


async def fail(context, rule, task, event=None):
    '''
    Task that deliberately raises an exception, thus exercising our
    failure handling code in a predictable way.

    '''
    rule.log.debug("Gating is {}".format(task.gating))

    message = "Deliberate Test Failure"

    if task.args.get('generic_exception'):
        raise Exception(message)
    if task.args.get('break_connection'):
        await asyncio.sleep(20)
        rule.log.debug("Generating connection failure")
        await context.juju_model.connection.ws.close()
        return True

    raise TestFailure(task, message=message)
