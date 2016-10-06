import asyncio
import logging
import sys
import uuid
from pathlib import Path

import attr


log = logging.getLogger("bus")


@attr.s
class Event:
    """A local or remote event tied to the context timeline."""
    time = attr.ib(init=False, convert=float)
    created = attr.ib(init=False)
    origin = attr.ib(init=False)   # an object or subsystem that spawned the event
    kind = attr.ib(init=False)     # a (dotted) string indicating the kind of event
    payload = attr.ib(default=None)  # object for payload, ex: kind based map

    def __str__(self):
        return "{} -> {} {!r}".format(self.origin, self.kind, self.payload)


class Bus:
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.__subscriptions = {}
        self.__queue = asyncio.Queue()
        self._exit_on_exception = False
        self.should_run = True

    def subscribe(self, subscriber, *conditions):
        if not callable(subscriber):
            raise TypeError("subscriber must be callable")
        for c in conditions:
            if not callable(c):
                raise TypeError("conditions must be callable {}".format(c))
        uid = uuid.uuid4()
        self.__subscriptions[uid] = (subscriber, conditions)
        return uid

    def unsubscribe(self, uid):
        self.__subscriptions.pop(uid, None)

    def dispatch(self, event=None, **kwargs):
        args = {}
        if isinstance(event, dict):
            args = event
        if not isinstance(event, Event):
            # create an event object from the args
            if kwargs:
                fields = attr.fields(Event)
                names = [f.name for f in fields]
                payload = args.setdefault("payload", kwargs.pop("payload", {}))
                for k, v in list(kwargs.items()):
                    if k not in names:
                        if isinstance(payload, dict):
                            payload[k] = kwargs.pop(k)
                    else:
                        args[k] = v
            event = Event()
            for k, v in args.items():
                setattr(event, k, v)

        # Add runtime information
        event.time = self.loop.time()
        if "created" not in kwargs:
            call_frame = sys._getframe(1)
            c = call_frame.f_code
            p = Path(c.co_filename)
            created = "{}:{}:{}::{}".format(
                    __package__,
                    p,
                    call_frame.f_lineno,
                    c.co_name)
            event.created = created
        # Fire
        self.__queue.put_nowait(event)

    async def notify(self, until_complete=False):
        # until_complete is used for simplified testing
        evt_ct = 0
        while True:
            # This check is mostly for testing on
            # an empty loop
            if self.__queue.qsize() == 0:
                if until_complete is True:
                    break
            event = await self.__queue.get()
            evt_ct += 1
            # Now push the event to subscribers
            applied = False
            subscriptions = list(self.__subscriptions.values())

            for subscriber, conditions in subscriptions:
                # Should this go back into the event loop? or can we count on
                # the subscriber to do the proper thing. If the idea is to keep
                # a journal with transaction like support, which is a lie as
                # the driver changes are not idempotent, then we must have some
                # support for the idea that the event has really been processed
                # at the end of this
                use = True

                for condition in conditions:
                    if not condition(event):
                        use = False
                        break
                if use is True:
                    try:
                        name = subscriber.__func__.__qualname__
                    except AttributeError:
                        name = str(subscriber)

                    log.debug("#%d %s -> %s", evt_ct, event, name)
                    applied = True

                    try:
                        if asyncio.iscoroutinefunction(subscriber):
                            await subscriber(event)
                        else:
                            subscriber(event)
                    except Exception:
                        log.warn("Exception %s for %s %d",
                                 subscriber.__func__.__qualname__,
                                 event,
                                 evt_ct,
                                 exc_info=True,
                                 stack_info=True)
                        if self._exit_on_exception is True:
                            self.shutdown()
                            return

            if not applied:
                log.debug("Unhandled event %s %d", event, evt_ct)

            # Track the event after it has been applied
            if self.__queue.qsize() == 0:
                if until_complete is True or self.should_run is False:
                    log.debug("Bus Complete, exiting")
                    break

    def shutdown(self):
        self.should_run = False


default_bus = None


def get_default_bus():
    global default_bus
    if not default_bus:
        set_default_bus()
    return default_bus


def set_default_bus(bus=None, loop=None):
    global default_bus
    if default_bus is not None:
        raise RuntimeError("Default Bus already set")

    if not bus:
        loop = loop or asyncio.get_event_loop()
        bus = Bus(loop=loop)

    default_bus = bus
