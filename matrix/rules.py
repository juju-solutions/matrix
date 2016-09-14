import asyncio
import functools
import json
import logging
import os
import sys
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
class Event:
    """A local or remote event tied to the context timeline."""
    time = attr.ib(convert=float)
    created = attr.ib()
    origin = attr.ib()
    message = attr.ib()
    details = attr.ib()

    def __str__(self):
        details = ''
        if self.details:
            details = "\n" + self.details
        return "{}{}".format(self.message, details)


@attr.s
class Timeline(list):
    """A timeline of events"""


@attr.s
class Context:
    loop = attr.ib()
    suite = attr.ib()
    timeline = attr.ib(init=False, default=attr.Factory(Timeline))
    states = attr.ib(init=False, default=attr.Factory(dict))
    config = attr.ib(repr=False)
    actions = attr.ib(default=attr.Factory(dict), repr=False, init=False)

    def set_state(self, name, value):
        self.states[name] = value

    def record(self, **kwargs):
        call_frame = sys._getframe(1)
        c = call_frame.f_code
        p = Path(c.co_filename)
        created = "{}.{}:{}::{}".format(
                __package__,
                p,
                call_frame.f_lineno,
                c.co_name)

        e = Event(
                time=self.loop.time(),
                created=created,
                **kwargs)
        self.timeline.append(e)

    def register_action(self, name, handler):
        self.actions[name] = handler


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
                cmd = utils._resolve(cmd)
                resolved = True
        context.actions[self.name] = cmd
        log.debug("Resolved %s to %s", self.command, cmd)
        return cmd

    async def execute(self, context, rule):
        cmd = self.resolve(context)
        if not cmd:
            raise ValueError(
                    "Unable to resolve action %s for rule %s",
                    rule.action, rule)
        context.set_state(rule.name, RUNNING)
        try:
            if isinstance(cmd, Path):
                result = await self.execute_process(context, cmd, rule)
            else:
                # this is a plugin. resolve would have loaded it
                result = await self.execute_plugin(context, cmd, rule)
                context.set_state(rule.name, DONE)
        except Exception:
            log.warn("Error in %s's action %s",
                     rule, rule.action, exc_info=True)
            raise

            return result

    async def execute_plugin(self, context, cmd, rule):
        # Run code that isn't a coro in an executor
        if not asyncio.iscoroutinefunction(cmd):
            ctxcmd = functools.partial(cmd, context, rule)
            return await context.loop.run_in_executor(ctxcmd)
        else:
            return await cmd(context, rule)

    async def execute_process(self, context, cmd, rule):
        def attr_filter(a, v):
            return a.name not in ["actions", "config", "loop"]

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
                log.debug(stdout.decode('utf-8'))
            if stderr:
                log.debug(stderr.decode('utf-8'))
            self.complete = p.returncode is 0
        except FileNotFoundError:
            log.warn("Action: {} not on path: {}".format(
                self.cmd, path))


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


@attr.s
class Rule:
    action = attr.ib()
    conditions = attr.ib(default=attr.Factory(list))
    complete = attr.ib(default=False, convert=bool)

    @property
    def name(self):
        return self.action.name

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
        return await self.action.execute(context, self)

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
    def __init__(self, loop=None):
        self.loop = loop if loop else asyncio.get_event_loop()
        self._reported = False

    def load_suite(self, filelike):
        log.info("Parsing %s" % filelike.name)
        tests = load_suite(filelike)
        context = Context(loop=self.loop, config=self, suite=tests)
        return context

    async def rule_runner(self, rule, context):
        result = None
        while True:
            if not rule.match(context):
                log.debug("rule '%s' blocked on %s. context: %s ",
                          rule.name, rule.pending(context), context.states)
                await asyncio.sleep(self.interval)
                if not rule.has("until"):
                    continue
            # The rules conditions were met
            # we should spawn the task and record states for it in context
            #context.set_state(rule.name, RUNNING)
            result = await rule.execute(context)
            # The rule has finished executing
            context.record(
                    message="Finished rule action: %s" % rule.name,
                    details=result,
                    origin=rule.name
                    )
            period = rule.action.args.get("periodic")
            if rule.has("until") or period:
                # we need some special handling for until conditions, these
                # don't terminate on their own (or rather they get restarted
                # until their condition is satisfied) so we must check here
                # if we should terminate
                # XXX: if we wanted to terminate a rule as soon at its
                # condition was met we'd have to run rule.execute in another
                # task and be able to terminate that from a check done after
                # any Context.set_state
                if all(not c.match(context) for c in rule.select("until")):
                    rule.complete = True
                    #context.set_state(rule.name, DONE)

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
        context.record(message="Start test: {} - {}".format(
            test.name, test.description),
                       details="",
                       origin="matrix")
        runners = []
        for rule in test.rules:
            task = self.loop.create_task(
                    self.rule_runner(rule, context))
            runners.append(task)
            context.record(
                    message="Create task {}".format(rule.name),
                    origin="matrix",
                    details="",
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
            log.critical("PENDING TASKS REMAIN %s", pending)
        else:
            #print(list(t.result() for t in done))
            success = all([bool(t.result()) for t in done])

        log.info("%s Complete %s", test.name, success)

    async def run(self, context):
        for test in context.suite:
            await self.run_once(context, test)
            context.states.clear()

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
        context = self.load_suite(self.config_file.open())
        reporter = functools.partial(self.report, context)
        self.loop.set_exception_handler(reporter)
        await self.run(context)
        self.loop.stop()
        self.report(context)
