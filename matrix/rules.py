import asyncio
import fnmatch
import functools
import io
import logging
import traceback
import yaml

import attr
import petname
import juju.model

from . import model
from .model import RUNNING, COMPLETE, PAUSED


log = logging.getLogger("matrix")
_marker = object()


def pet_test():
    return petname.Generate(2, ".")


@attr.s
class Test:
    """
    Tests are a list of rules which execute via a small rule engine.
    """
    name = attr.ib(default=attr.Factory(pet_test))
    description = attr.ib(default="")
    rules = attr.ib(default=attr.Factory(list))
    result = attr.ib(default=None, init=False)

    def complete(self, context):
        return all([r.complete(context) for r in self])

    @classmethod
    def from_spec(cls, data, fmt):
        ins = cls()
        m = getattr(ins, "from_v%s" % (fmt))
        if not m:
            raise ValueError("Rule in invalid format: %s" % (fmt))
        m(data)
        return ins

    def from_v1(self, data):
        name = data.get("name")
        if name:
            self.name = name
        desc = data.get("description")
        if desc:
            self.description = desc

        for d in data['rules']:
                aspec = d.get("do")
                if not aspec:
                    raise ValueError(
                            "'do' clause required for each rule: %s" % d)
                if isinstance(aspec, dict):
                    # Create valid Action instance
                    do = aspec.pop("action")
                else:
                    do = aspec
                    aspec = {}
                action = model.Action(do, aspec)

                conditions = []
                for phase in ["when", "after", "until",
                              "while", "on", "periodic"]:
                    # create valid Condition instances
                    if phase not in d:
                        continue
                    v = d.get(phase)
                    if v:
                        if isinstance(v, str):
                            v = v.rsplit(".", 1)
                        conditions.append(
                                model.Condition(
                                    mode=phase,
                                    statement=v))

                self.rules.append(model.Rule(action, conditions))

    def match(self, context):
        """Return list of matching rules given context"""
        return [r for r in self.rules if r.match(context)]


class Suite(list):
    @classmethod
    def from_spec(cls, data):
        fmt = int(data.get("fmt", 1))
        ins = cls()
        m = getattr(ins, "from_v%s" % (fmt))
        if not m:
            raise ValueError("Tests in invalid format: %s" % (fmt))
        m(data, fmt)
        return ins

    def from_v1(self, data, fmt, factory=Test):
        for test in data['tests']:
            self.append(factory.from_spec(test, fmt))

    def append(self, test):
        if not isinstance(test, Test):
            raise TypeError("Tests are built of test instances, see docs")
        super(Suite, self).append(test)


def load_suite(filelike, factory=Suite):
    spec = yaml.load(filelike)
    rules = factory.from_spec(spec)
    return rules


class RuleEngine:
    def __init__(self, bus):
        self.loop = bus.loop
        self.bus = bus

        self._reported = False

    def load_suite(self, filelike):
        log.info("Parsing %s" % filelike.name)
        tests = load_suite(filelike)
        context = model.Context(
                loop=self.loop,
                bus=self.bus,
                config=self,
                juju_model=juju.model.Model(self.loop),
                suite=tests)
        return context

    async def rule_runner(self, rule, context):
        result = None
        self.bus.dispatch(
                kind="rule.create",
                payload=dict(rule=rule, result=None),
                origin="matrix",
        )
        subscription = None
        period = None
        if rule.has("periodic"):
            period = rule.select_one("periodic").statement

        while True:
            # ENTER
            if not rule.match(context) or subscription is not None:
                if not subscription:
                    log.debug("rule '%s' blocked on %s. context: %s ",
                              rule.name, rule.pending(context), context.states)
                await asyncio.sleep(self.interval, loop=self.loop)

            rule.lifecycle(context, RUNNING)
            if rule.has("on"):
                if subscription is None:
                    # subscribe the rules action
                    # The execution is managed by the subscription
                    # however, we check here if the termination
                    # conditions have been met.
                    # XXX: "on" events expect an "until" clause to handle their
                    # exit
                    subscription = await rule.setup_event(context)
                    log.debug("Subscribed  'on' event %s", rule)
            else:
                # RUN
                # The rules conditions were met
                # we should spawn the task and record states for it in context
                result = await rule.execute(context)

            # EXIT
            if rule.has("until"):
                # until conditions enter when they haven't been met, so to
                # exit we ask if all the until conditions for a rule
                # have been met (hence the not)
                if all(not c.match(
                        context, rule) for c in rule.select("until")):
                    rule.complete(context, True)

            if rule.complete(context):
                if subscription:
                    self.bus.unsubscribe(subscription)
                    result = True
                    log.debug("Unsubscribed  'on' event %s", rule)
                break
            elif period:
                # our example uses periodic to do health checks
                # in reality we will want rule_runner to block on
                # a lock/condition such that we don't progress testing
                # until we've assessed system health
                rule.lifecycle(context, PAUSED)
                await asyncio.sleep(period, loop=self.loop)
                rule.lifecycle(context, RUNNING)

        self.bus.dispatch(
                kind="rule.done",
                payload=dict(rule=rule, result=result),
                origin=rule.name
                )
        return result

    async def run_once(self, context, test):
        # Attempt each rule in the test
        # if it matches we can trigger it
        # setting states as needed.
        success = False
        self.bus.dispatch(
                kind="test.start",
                payload=test,
                origin="matrix")
        runners = []
        for rule in test.rules:
            task = self.loop.create_task(
                    self.rule_runner(rule, context))
            runners.append(task)
            untils = rule.select("until")
            if untils:
                # The rule should terminate when a state is set, we want this
                # to happen ASAP and not at the end of some long (or infinite)
                # tasks completion. For this to happen we push the task objects
                # onto a list of waiters in the context. When states are set we
                # check that list and on a match cancel() each task that was
                # "until" the state was set.
                for u in untils:
                    w = context.waiters.setdefault(u.name, [])
                    log.debug(
                            "Adding task to wait list on %s for rule %s",
                            u.name, rule.name)
                    w.append((task, rule))

        # rule_runner will run each rule to completion
        # (either success or failure) and then terminate here
        done, pending = await asyncio.wait(
                runners, loop=self.loop,
                return_when=asyncio.FIRST_EXCEPTION)
        if pending:
            # We terminated with things still running
            # this could be a test failure or poor rule formation.
            # can we do anything here
            log.warn("Pending tasks remain, aborting due to failure")

        exceptions = [t for t in done if t.exception()]
        if exceptions:
            for t in exceptions:
                s = io.StringIO()
                t.print_stack(file=s)
                log.error("Exception processing test: %s\n%s",
                          test.name,
                          s.getvalue())
        else:
            success = all([bool(t.result()) for t in done])
        test.result = success
        log.info("%s Complete %s", test.name, success)
        self.bus.dispatch(
                kind="test.complete",
                origin="matrix",
                payload=test)
        return success

    async def run(self, context):
        def allow_event(e):
            for fn in ["logging.*", "test.schedule"]:
                if fnmatch.fnmatch(e.kind, fn):
                    return False
            return True

        self.bus.subscribe(context.timeline.append,
                           allow_event)

        # reduce the test set to those matching pattern
        suite = []
        for t in context.suite:
            for tp in self.test_pattern:
                if fnmatch.fnmatch(t.name, tp):
                    suite.append(t)
                    break
        context.suite = suite

        self.bus.dispatch(
                origin="matrix",
                kind="test.schedule",
                payload=context.suite)
        for test in context.suite:
            await self.run_once(context, test)
            context.states.clear()
            context.waiters.clear()

        self.bus.dispatch(
                origin="matrix",
                kind="test.finish",
                payload=context
        )

    def exception_handler(self, context, loop=None, exc_ctx=None):
        if exc_ctx:
            log.debug(exc_ctx["message"])
            e = exc_ctx.get("exception")
            if e:
                log.warn("\n".join(
                    traceback.format_exception(type(e), e, e.__traceback__)))

        if self._reported:
            return
        self._reported = True

    async def model_change(self, delta, old_obj, new_obj, juju_model):
        self.bus.dispatch(
            kind="model.change",
            payload={
                'delta': delta,
                'old_obj': old_obj,
                'new_obj': new_obj,
            })

    async def __call__(self):
        btask = self.loop.create_task(self.bus.notify(False))
        context = self.load_suite(self.config_file)
        reporter = functools.partial(self.exception_handler, context)
        self.loop.set_exception_handler(reporter)
        try:
            # TODO: Create model per test, or model per suite
            await context.juju_model.connect_current()
            context.juju_model.add_observer(self.model_change)
            await self.run(context)
        finally:
            await context.juju_model.disconnect()
            # Wait for any unprocessed events before exiting the loop
            await btask
            self.loop.stop()
