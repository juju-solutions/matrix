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

RUNNING = "running"
DONE = "done"

log = logging.getLogger("matrix")


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
        if old_value != value:
            self.bus.dispatch(kind="state.change",
                              origin="context",
                              name=name,
                              old_value=old_value,
                              new_value=value)

    def __str__(self):
        return "Context object"


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

    async def execute_event(self, context, rule):
        # create and manage an event subscriber
        # for the condition in an "on" clause
        # when the "on" condition's statement is matched
        # to event.kind we use the curried handler
        # additionally passing the event itself.
        # XXX: this changes the call signature from other types of
        # plugins, maybe that additionally needs kwargs
        # call sig: callback(context, rule, action, event)
        cmd = self.resolve(context)
        async def event_wrapper(event):
            if isinstance(cmd, Path):
                callback = self.execute_process
            else:
                callback = self.execute_plugin
            return await callback(context, cmd, rule, event)

        # XXX: handle in loop?
        on_cond = rule.select("on")[0]

        def is_cond(e):
            return fnmatch.fnmatch(e.kind, on_cond.statement[0])
        return context.bus.subscribe(event_wrapper, is_cond)

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
            result = p.returncode is 0
        except FileNotFoundError:
            log.warn("Action: {} not on path: {}".format(
                self.cmd, path))
        return result


@attr.s
class Condition:
    # mode: trigger keys, see below
    mode = attr.ib()
    # statement: [<statename>, DONE|RUNNING]
    statement = attr.ib()

    TRIGGERS = {
            "after": [DONE],
            "while": [RUNNING],
            "when": [RUNNING, DONE],
            "until": lambda c, r: r != c.statement[1],
            "on": lambda c, r: True,  # bus event triggers only on conditions
                                      # don't block rule activation by
                                      # themselves
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

    async def execute_event(self,  context):
        result = await self.action.execute_event(context, self)
        return result

    async def execute(self, context):
        result = await self.action.execute(context, self)
        self.complete = result is True
        return result

    def asdict(self, result=None):
        data = attr.asdict(self)
        data['name'] = self.name
        data['result'] = result
        return data
