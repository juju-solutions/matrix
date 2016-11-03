
import asyncio

async def health2(context, rule, action, event=None):
    rule.log.info("Start Health")
    for i in range(1, action.args.get("duration", 15)):
        await asyncio.sleep(1, loop=context.loop)
        rule.log.info("DOING HEALTH CHECK %s %s", i, context.states.get("health2.state"))
        if i > 10:
            context.set_state("health2.state", "healthy")
        elif i > 5:
            context.set_state("health2.state", "sick")
        else:
            # It is unset at first
            pass
    rule.log.info("Stop health")
    return True
