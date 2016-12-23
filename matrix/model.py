import asyncio
import fnmatch
import functools
import json
import logging
import os
import time

import attr
from pathlib import Path

from . import utils

PENDING = "pending"
RUNNING = "running"
PAUSED = "paused"
COMPLETE = "complete"

_marker = object()
log = logging.getLogger("matrix")


class TestFailure(Exception):
    "Indicate that a test has failed"
    def __init__(self, task):
        self.task = task


@attr.s
class Event:
    """A local or remote event tied to the context timeline."""
    time = attr.ib(init=False, convert=float)
    created = attr.ib(init=False)
    origin = attr.ib(init=False)   # subsystem that spawned the event
    kind = attr.ib(init=False)     # a string indicating the kind of event
    payload = attr.ib(default=None)  # object for payload, ex: kind based map

    def __str__(self):
        return "{}:{}:: {} {}\n{!s}".format(
                time.ctime(self.time),
                self.created,
                self.origin,
                self.kind,
                self.payload)


@attr.s
class Timeline(list):
    """A timeline of events"""


@attr.s
class Context:
    loop = attr.ib(repr=False)
    bus = attr.ib(repr=False)
    suite = attr.ib()
    timeline = attr.ib(init=False, default=attr.Factory(Timeline))
    # Task -> State + (any custom states)
    states = attr.ib(init=False, default=attr.Factory(dict))
    # Top level config
    config = attr.ib(repr=False)
    # Resolve rule.task handlers
    tasks = attr.ib(default=attr.Factory(dict), repr=False, init=False)
    # Task cancellation callbacks
    # XXX: use an event for this?
    waiters = attr.ib(default=attr.Factory(dict), repr=False, init=False)
    juju_controller = attr.ib(repr=False)
    juju_model = attr.ib(repr=False, init=False)
    test = attr.ib(repr=False, init=False)

    def set_state(self, name, value):
        old_value = self.states.get(name, _marker)
        self.states[name] = value
        # Cancel any tasks blocked on this state/value
        # combination
        if self.waiters:
            waiters = self.waiters.get(".".join((name, value)), [])
            if COMPLETE == value:
                # allow "until: foo" as a shorthand for "until: foo.complete"
                waiters.extend(self.waiters.get(name, []))
            for t, owner in waiters:
                t.cancel()
        if old_value != value:
            self.bus.dispatch(kind="state.change",
                              origin="context",
                              name=name,
                              old_value=old_value,
                              new_value=value)

    def __str__(self):
        return "Context object"


@attr.s
class Task:
    command = attr.ib(convert=str)
    args = attr.ib(default=attr.Factory(dict))
    gating = attr.ib(default=True, convert=bool)

    @property
    def name(self):
        cmd = self.command
        if "." in cmd:
            cmd = cmd.rsplit(".", 1)[1]
        return str(cmd)

    def resolve(self, context):
        resolved = False
        cmd = context.tasks.get(self.command)
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
        context.tasks[self.name] = cmd
        log.debug("Resolved %s to %s", self.command, cmd)
        return cmd

    async def setup_event(self, context, rule):
        # create and manage an event subscriber
        # for the condition in an "on" clause
        # when the "on" condition's statement is matched
        # to event.kind we use the curried handler
        # additionally passing the event itself.
        # XXX: this changes the call signature from other types of
        # plugins, maybe that additionally needs kwargs
        # call sig: callback(context, rule, task, event)
        cmd = self.resolve(context)
        async def event_wrapper(event):
            if isinstance(cmd, Path):
                callback = self.execute_process
            else:
                callback = self.execute_plugin
            return await callback(context, cmd, rule, event)

        # XXX: handle in loop?
        on_cond = rule.select_one("on")

        def is_cond(e):
            return (fnmatch.fnmatch(e.kind, on_cond.name) and
                    rule.lifecycle(context) == RUNNING)
        return context.bus.subscribe(event_wrapper, is_cond)

    async def execute(self, context, rule):
        # create a log object for context
        cmd = self.resolve(context)
        if not cmd:
            raise ValueError(
                    "Unable to resolve task %s for rule %s",
                    rule.task, rule)
        result = False
        try:
            if isinstance(cmd, Path):
                result = await self.execute_process(context, cmd, rule)
            else:
                # this is a plugin. resolve would have loaded it
                result = await self.execute_plugin(context, cmd, rule)
        except asyncio.CancelledError:
            result = True
            log.debug("Cancelled %s", rule.name)
        except Exception:
            log.warn("Error in %s's task %s",
                     rule, rule.task, exc_info=True)
            raise

        return result

    async def execute_plugin(self, context, cmd, rule, event=None):
        # Run code that isn't a coro in an executor
        if not asyncio.iscoroutinefunction(cmd):
            ctxcmd = functools.partial(cmd, context, rule, self, event)
            result = await context.loop.run_in_executor(ctxcmd)
        else:
            result = await cmd(context, rule, self, event)
        return result

    async def execute_process(self, context, cmd, rule, event=None):
        def attr_filter(a, v):
            return a.repr is True
        data = attr.asdict(
                context,
                recurse=True,
                filter=attr_filter)
        data['args'] = self.args
        if event:
            data['event'] = attr.asdict(
                    event, recurse=True,
                    filter=attr_filter)

        data = json.dumps(data).encode("utf-8")
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
            result = p.returncode == 0
            if not result:
                raise TestFailure
        except FileNotFoundError:
            log.warn("Task: {} not on path: {}".format(
                self.cmd, path))
        return result


def always_trigger(context, rule, condition):
    return True


def until_trigger(context, rule, condition):
    # ex: statement will be like deploy.complete or
    # health.status.healthy
    if "." in condition.statement:
        k, v = condition.statement.rsplit(".", 1)
        v = [v]
    else:
        k = condition.statement
        v = None
    if not v:
        return k not in condition.states
    return k not in context.states or context.states[k] not in v


@attr.s
class Condition:
    # mode: trigger keys, see below
    mode = attr.ib()
    # statement is the state that must match the condition in ctx states
    # this will be modified by TRIGGERS if the statement isn't a dotted name
    statement = attr.ib()

    TRIGGERS = {
            "after": [COMPLETE],
            "while": [RUNNING, PAUSED],
            "when": [RUNNING, COMPLETE, PAUSED],
            "until": [],
            "on": always_trigger,  # bus event triggers only on
                                   # conditions don't block rule
                                   # activation by themselves
            "periodic": always_trigger,
            }

    def match(self, context, rule):
        """Resolve the state listed in statement from the context"""
        # Map any state to a name, resolve that name in context.states
        matchers = self.TRIGGERS[self.mode]
        if callable(matchers):
            # There will only be one callable in this case
            # XXX: we might want to return the list of states
            # directly and continue our normal tests here
            return matchers(context, rule, self)
        else:
            # we test that both the state exists and that its value is
            # in a set specified in the config or falling back
            # to the states that are valid and defined in TRIGGERS
            # for a given key word
            if "." in self.statement:
                k, v = self.statement.rsplit(".", 1)
                v = [v]
            else:
                k = self.statement
                v = self.TRIGGERS[self.mode]
            result = k in context.states and context.states[k] in v
            if self.mode == "until":
                result = not result
            return result

    def __str__(self):
        return "%s:%s" % (self.mode, self.statement)

    @property
    def name(self):
        return self.statement


@attr.s
class Rule:
    task = attr.ib()
    conditions = attr.ib(default=attr.Factory(list))

    @property
    def name(self):
        return self.task.name

    @property
    def log(self):
        return logging.getLogger(self.name)

    def lifecycle(self, context, value=_marker):
        name = self.name
        if value is not _marker:
            context.set_state(name, value)
        return context.states[name]

    def complete(self, context, value=_marker) -> bool:
        name = self.name
        if value is not _marker:
            value = bool(value)
            if value is True:
                self.lifecycle(context, COMPLETE)
        return bool(context.states.get(name, False) == COMPLETE)

    def match(self, context):
        if not self.conditions:
            return True
        results = [c.match(context, self) for c in self.conditions]
        return all(results)

    def pending(self, context):
        return [c for c in self.conditions if not c.match(context, self)]

    def has(self, condition_clause):
        return any(self.select(condition_clause))

    def select(self, clause):
        return [c for c in self.conditions if c.mode == clause]

    def select_one(self, clause):
        r = self.select(clause)
        if not r:
            return None
        return r[0]

    async def setup_event(self,  context):
        result = await self.task.setup_event(context, self)
        return result

    async def execute(self, context):
        result = await self.task.execute(context, self)
        return result
