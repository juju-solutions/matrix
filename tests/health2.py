
import asyncio

async def health2(context, rule, action, event=None):
    rule.log.info("Start Health")
    try:
        for i in range(1, action.args.get("duration", 15)):
            await asyncio.sleep(1, loop=context.loop)
            if i > 10:
                context.set_state("health.state", "healthy")
            elif i > 5:
                context.set_state("health.state", "sick")
            else:
                # It is unset at first
                pass
    except asyncio.CancelledError:
        pass
    rule.log.info("Stop health")
    return True
