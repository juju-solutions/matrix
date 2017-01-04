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
    else:
        raise TestFailure(task, message=message)
