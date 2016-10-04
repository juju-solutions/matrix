import asyncio
import functools
import io
import json
import logging
import os
import traceback
import yaml
from pathlib import Path

import attr
import petname

from . import utils


log = logging.getLogger("matrix")
_marker = object()

RUNNING = "running"
DONE = "done"


def pet_test():
    return petname.Generate(2, ".")


@attr.s
class Timeline(list):
    """A timeline of events"""


@attr.s
class Context:
    loop = attr.ib(repr=False)
    bus = attr.ib(repr=False)
    suite = attr.ib()
    timeline = attr.ib(init=False, default=attr.Factory(Timeline))
    states = attr.ib(init=False, default=attr.Factory(dict))
    config = attr.ib(repr=False)
    actions = attr.ib(default=attr.Factory(dict), repr=False, init=False)
    waiters = attr.ib(default=attr.Factory(dict), repr=False, init=False)

    def set_state(self, name, value):
        old_value = self.states.get(name)
        self.states[name] = value
        # Cancel any tasks blocked on this state
        waitname = ".".join((name, value))
        for t in self.waiters.get(waitname, []):
            t.cancel()
        self.bus.dispatch(kind="state.change",
                          origin="context",
                          name=name,
                          old_value=old_value,
                          new_value=value)


@attr.s
class Action:
    command = attr.ib(convert=str)
    args = attr.ib(default=attr.Factory(dict))

    @property
    def name(self):
        cmd = self.command
        if "." in cmd:
            cmd = cmd.rsplit(".", 1)[1]
        return str(cmd)

    def resolve(self, context):
        resolved = False
        cmd = context.actions.get(self.command)
        if cmd is not None:
            return cmd
        cmd = None
        names = [Path(self.command),
                 Path(context.config.path) / Path(self.command)]
        for n in names:
            if n.exists():
                cmd = n
                resolved = True
                break

        if not resolved:
            # we didn't find cmd on the path
            # we can see if its a plugin
            cmd = self.command
            if "." in cmd:
                # This will throw ImportError on failure
                cmd = utils.resolve_dotpath(cmd)
                resolved = True
        context.actions[self.name] = cmd
        log.debug("Resolved %s to %s", self.command, cmd)
        return cmd

    async def execute(self, context, rule):
        # create a log object for context
        cmd = self.resolve(context)
        if not cmd:
            raise ValueError(
                    "Unable to resolve action %s for rule %s",
                    rule.action, rule)
        result = False
        try:
            if isinstance(cmd, Path):
                result = await self.execute_process(context, cmd, rule)
            else:
                # this is a plugin. resolve would have loaded it
                result = await self.execute_plugin(context, cmd, rule)
                context.set_state(rule.name, DONE)
        except asyncio.CancelledError:
            result = True
            log.debug("Cancelled %s", rule.name)
        except Exception:
            log.warn("Error in %s's action %s",
                     rule, rule.action, exc_info=True)
            raise

        return result

    async def execute_plugin(self, context, cmd, rule):
        # Run code that isn't a coro in an executor
        if not asyncio.iscoroutinefunction(cmd):
            ctxcmd = functools.partial(cmd, context, rule)
            result = await context.loop.run_in_executor(ctxcmd)
        else:
            result = await cmd(context, rule)
        return result

    async def execute_process(self, context, cmd, rule):
        def attr_filter(a, v):
            return a.repr is True

        data = json.dumps(attr.asdict(
                            context,
                            recurse=True,
                            filter=attr_filter)).encode("utf-8")
        path = "{}:{}".format(str(context.config.path),
                              os.environ.get("PATH", ""))
        try:
            p = await asyncio.create_subprocess_exec(
                    str(cmd),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={"PATH": path}
                    )
            stdout, stderr = await p.communicate(data)
            log.debug("Exec %s -> %d", cmd, p.returncode)
            if stdout:
                rule.log.debug(stdout.decode('utf-8'))
            if stderr:
                rule.log.debug(stderr.decode('utf-8'))
            result = p.returncode is 0
        except FileNotFoundError:
            log.warn("Action: {} not on path: {}".format(
                self.cmd, path))
        return result


@attr.s
class Condition:
    mode = attr.ib()
    statement = attr.ib()

    TRIGGERS = {
            "after": [DONE],
            "while": [RUNNING],
            "when": [RUNNING, DONE],
            "until": lambda c, r: r != c.statement[1]
            }

    def resolve(self, context):
        """Resolve the state listed in statement from the context"""
        state = self.statement[0]
        return context.states.get(state)

    def match(self, context):
        result = self.resolve(context)
        allowed = self.TRIGGERS.get(self.mode)
        if callable(allowed):
            return allowed(self, result)
        return result in allowed

    @property
    def name(self):
        return ".".join(self.statement)


@attr.s
class Rule:
    action = attr.ib()
    conditions = attr.ib(default=attr.Factory(list))
    complete = attr.ib(default=False, convert=bool)

    @property
    def name(self):
        return self.action.name

    @property
    def log(self):
        return logging.getLogger(self.name)

    def match(self, context):
        if not self.conditions:
            return True
        return all([c.match(context) for c in self.conditions])

    def pending(self, context):
        return [c for c in self.conditions if not c.match(context)]

    def has(self, condition_clause):
        return any(self.select(condition_clause))

    def select(self, clause):
        return [c for c in self.conditions if c.mode == clause]

    async def execute(self, context):
        result = await self.action.execute(context, self)
        self.complete = result is True
        return result

    async def until(self, context):
        while True:
            # make sure we execute at least once
            await self.execute()

            # test the condition
            results = [c.resolve(context) for c in self.select("until")]
            if all(results):
                # when all until clauses are matched
                # we can break the loop
                break


@attr.s
class Test:
    """
    Tests are a list of rules which execute via a small rule engine.
    """
    name = attr.ib(default=attr.Factory(pet_test))
    description = attr.ib(default="")
    rules = attr.ib(default=attr.Factory(list))

    @property
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
                action = Action(do, aspec)

                conditions = []
                for phase in ["when", "after", "until", "while"]:
                    # create valid Condition instances
                    if phase not in d:
                        continue
                    v = d.get(phase)
                    if v and "." in v:
                        v = v.split(".", 1)
                    else:
                        v = [v, DONE]
                    if v:
                        conditions.append(Condition(mode=phase, statement=v))

                self.rules.append(Rule(action, conditions))

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
        context = Context(loop=self.loop,
                          bus=self.bus,
                          config=self,
                          suite=tests)
        return context

    async def rule_runner(self, rule, context):
        result = None
        while True:
            # ENTER
            if not rule.match(context):
                log.debug("rule '%s' blocked on %s. context: %s ",
                          rule.name, rule.pending(context), context.states)
                await asyncio.sleep(self.interval, loop=self.loop)

            # RUN
            # The rules conditions were met
            # we should spawn the task and record states for it in context
            context.set_state(rule.name, RUNNING)
            result = await rule.execute(context)
            # The rule has finished executing
            self.bus.dispatch(
                    kind="rule.done",
                    payload=result,
                    origin=rule.name
                    )

            # EXIT
            period = rule.action.args.get("periodic")
            if rule.has("until"):
                # we need some special handling for until conditions, these
                # don't terminate on their own (or rather they get restarted
                # until their condition is satisfied) so we must check here
                # if we should terminate
                if all(not c.match(context) for c in rule.select("until")):
                    rule.complete = True

            if rule.complete:
                context.set_state(rule.name, DONE)
                break
            elif period:
                # our example uses periodic to do health checks
                # in reality we will want rule_runner to block on
                # a lock/condition such that we don't progress testing
                # until we've assessed system health
                await asyncio.sleep(period, loop=self.loop)
        return result

    async def run_once(self, context, test):
        # Attempt each rule in the test
        # if it matches we can trigger it
        # setting states as needed.
        success = False
        self.bus.dispatch(
                kind="test.start",
                payload="{} - {}".format(test.name, test.description),
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
                    w.append(task)

            self.bus.dispatch(
                    kind="rule.create",
                    payload=rule,
                    origin="matrix",
                    )

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

        log.info("%s Complete %s", test.name, success)
        payload = attr.asdict(test)
        payload['result'] = success
        self.bus.dispatch(
                origin="matrix",
                kind="test.complete",
                payload=payload)
        return success

    async def run(self, context):
        self.bus.dispatch(
                origin="matrix",
                kind="test.schedule",
                payload=context.suite)
        for test in context.suite:
            result = await self.run_once(context, test)
            context.states.clear()
            context.waiters.clear()
            payload = attr.asdict(test)
            payload['result'] = result
            self.bus.dispatch(
                    origin="matrix",
                    kind="test.complete",
                    payload=payload)

    def report(self, context, loop=None, exc_ctx=None):
        if exc_ctx:
            log.debug(exc_ctx["message"])
            e = exc_ctx.get("exception")
            if e:
                log.warn("\n".join(
                    traceback.format_exception(type(e), e, e.__traceback__)))

        if self._reported:
            return
        self._reported = True
        if self.show_report:
            log.info("Generating Report...")
            for event in context.timeline:
                log.info(event)
        if exc_ctx:
            self.loop.stop()

    async def __call__(self):
        try:
            context = self.load_suite(self.config_file)
            reporter = functools.partial(self.report, context)
            self.loop.set_exception_handler(reporter)
            await self.run(context)
            self.report(context)
        except:
            self.loop.stop()
            raise
        else:
            self.loop.stop()
