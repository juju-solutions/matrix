import asyncio
import collections
import datetime
import logging
import os
from time import time
from xml.etree.ElementTree import Element, SubElement, tostring

import urwid

from .bus import eq, prefixed
from .model import PENDING, RUNNING, PAUSED, COMPLETE

log = logging.getLogger("view")

palette = [
        ("default", "default", "default"),
        ("header", "white", "default", "standout"),
        ("pass", "dark green", "default"),
        ("fail", "dark red", "default"),
        ("focused", "black", "dark cyan", "standout"),
        ("DEBUG", "yellow", "default"),
        ("INFO", "default", "default"),
        ("WARN", "dark cyan", "default"),
        ("CRITICAL", "fail"),
        ]


TEST_SYMBOLS = {
        True: ("pass", "\N{HEAVY CHECK MARK}"),
        False: ("fail", "\N{HEAVY BALLOT X}"),
        }

STATE_SYMNOLS = {
        PENDING: ("default", PENDING),
        PAUSED: ("default", PAUSED),
        RUNNING: ("pass", RUNNING),
        COMPLETE: ("pass", COMPLETE)
        }


def identity(o):
    return o


class SimpleDictValueWalker(urwid.ListWalker):
    def __init__(self, body=None, factory=dict,
                 key_func=identity,
                 widget_func=urwid.Text):
        if body is None:
            body = factory()
        self.body = body
        self.key_func = key_func
        self.widget_func = widget_func
        self.focus = 0

    def __getitem__(self, pos):
        if isinstance(pos, int):
            keys = list(self.body.keys())
            k = keys[pos]
            o = self.body[k]
        else:
            o = self.body[pos]
        return self.widget_func(o)

    def update(self, entity, focus=True):
        key = self.key_func(entity)
        self.body[key] = entity
        if focus:
            pos = self._get_pos(key)
            self.set_focus(pos)
        else:
            self._modified()

    def _get_pos(self, pos, offset=None):
        keys = list(self.body.keys())
        if not isinstance(pos, int):
            obj = self.body[pos]
            key = self.key_func(obj)
            for i, k in enumerate(keys):
                if k == key:
                    pos = i
                    break

        if offset:
            pos = pos + offset
            if pos < 0 or pos > len(keys):
                raise IndexError("Unable to offset position")
        return pos

    def next_position(self, pos):
        return self._get_pos(pos, 1)

    def prev_position(self, pos):
        return self._get_pos(pos, -1)

    def set_focus(self, position):
        self.focus = self._get_pos(position)
        self._modified()


class SimpleListRenderWalker(urwid.ListWalker):
    def __init__(self, body, widget_func=urwid.Text):
        self.body = body
        self.widget_func = widget_func
        self.focus = 0

    def __getitem__(self, pos):
        o = self.body[pos]
        return self.widget_func(o)

    def update(self, entity, pos=-1, focus=True):
        if pos == -1:
            self.body.append(entity)
            pos = len(self.body) - 1
        else:
            self.body[pos] = entity
        if focus:
            self.set_focus(pos)
        else:
            self._modified()

    def _pos(self, pos, offset=None):
        if offset:
            pos = pos + offset
            if pos < 0 or pos > len(self.body):
                raise IndexError("Unable to offset position")
        return pos

    def next_position(self, pos):
        return self._pos(pos, 1)

    def prev_position(self, pos):
        return self._pos(pos, -1)

    def set_focus(self, position):
        self.focus = self._pos(position)
        self._modified()


class Viewlet(urwid.WidgetWrap):
    pass


class Lines(Viewlet):
    def __init__(self, model=None, widget_func=urwid.Text):
        if model is None:
            model = []
        self.m = model
        self.walker = SimpleListRenderWalker(
                self.m, widget_func=widget_func)
        self._w = urwid.ListBox(self.walker)

    def update(self, entity, pos=-1, focus=True):
        self.walker.update(entity, pos=pos, focus=focus)

    def _modified(self):
        self.walker._modified()


class View(urwid.WidgetWrap):
    def __init__(self, bus, context, screen=None):
        self.bus = bus
        self.context = context
        self.screen = screen
        self._w = self.build_ui()
        self.subscribe()
        self._input_mode = "default"

    @property
    def input_mode(self):
        return self._input_mode

    @input_mode.setter
    def input_mode(self, value):
        self.bus.dispatch(kind="ui.change", payload=value)
        self._input_mode = value

    def build_ui(self):
        pass

    def subscribe(self):
        pass

    def input_handler(self, ch):
        pass


class SelectableText(urwid.Edit):
    def valid_char(self, ch):
        return False


def chop_microseconds(delta):
    return delta - datetime.timedelta(microseconds=delta.microseconds)


def render_task_row(row):
    rule = row['rule']
    state = row.get("state", PENDING)
    output = [
        "{:18} -> ".format(rule.name),
        state.ljust(15),
        " "
            ]
    result = row.get("result")
    if result:
        output.append(TEST_SYMBOLS[result])
    return SelectableText(output)


def render_status(entry):
    if isinstance(entry, str):
        msg = entry
    else:
        msg = [(entry.levelname, entry.output)]

    return SelectableText(msg, wrap="space")


def render_test(test_row):
    t = test_row["test"]
    result = test_row["result"]

    output = [t.name.ljust(18)]
    if result in TEST_SYMBOLS:
        duration = None
        stop = test_row.get("stop")
        if not stop:
            stop = asyncio.get_event_loop().time()
        duration = stop - test_row["start"]
        duration = chop_microseconds(datetime.timedelta(seconds=duration))
        output.append(" {}\N{TIMER CLOCK}  ".format(duration))
    output.append(TEST_SYMBOLS.get(result, result))
    return urwid.Text(output)


def fetch_name(obj):
    return obj['test'].name


class TUIView(View):
    # Commands is a nested dict with [mode]: {"k": callsignature}
    KEY_MAP = {
            "default": {
                "_master": True,
                "q": "quit",
                "t": "toggle timeline",
                }
            }

    UI_ACTIONS = {
            "quit": "quitter",
            "toggle timeline": "toggle_timeline",
            }

    def build_ui(self):
        widgets = []

        self.tests = collections.OrderedDict()
        self.test_walker = SimpleDictValueWalker(
                self.tests,
                key_func=fetch_name,
                widget_func=render_test)
        self.test_view = urwid.ListBox(self.test_walker)
        self.bus.subscribe(self.handle_tests, prefixed("test."))

        self.tasks = collections.OrderedDict()
        self.task_walker = SimpleDictValueWalker(
                self.tasks,
                key_func=lambda o: o.name,
                widget_func=render_task_row)
        self.task_view = urwid.ListBox(self.task_walker)
        self.bus.subscribe(self.show_rule_state, prefixed("rule."))
        self.bus.subscribe(self.show_state_change, eq("state.change"))

        widgets.append(("weight", 0.6, urwid.Columns([
            urwid.LineBox(self.test_view, "Tests"),
            urwid.LineBox(self.task_view, "Tasks")
            ])))

        self.status = Lines(
                collections.deque([], 100),
                widget_func=render_status)
        self.bus.subscribe(self.show_log, eq("logging.message"))

        self.running = True
        self.model = Lines()
        # Ideally libjuju provides something like this
        self.model_watcher = asyncio.get_event_loop().create_task(
                self.watch_juju_status())

        self.debug = Lines(collections.deque([], 200))
        self.debug_watcher = asyncio.get_event_loop().create_task(
                self.debug_juju_log())

        widgets.append(("weight", 2, urwid.Columns([
            urwid.LineBox(self.status, "Status Log"),
            urwid.Pile([
                urwid.LineBox(self.model, "Juju Model"),
                ("weight", 0.6, urwid.LineBox(self.debug, "Juju Debug")),
                ])
            ])))

        self.pile = body = urwid.Pile(widgets)
        self.frame = urwid.Frame(
                header=urwid.Text("Matrix Test Runner"),
                body=body)

        #  Timeline widget
        self.timeline = Lines(self.context.timeline)
        self.bus.subscribe(self.populate_timeline,  eq("state.change"))
        self.bus.subscribe(self.populate_timeline,  eq("model.change"))

        # Footer
        self.control_bar = urwid.Text("")
        self.frame.footer = self.control_bar
        self.bus.subscribe(self.show_keymap, eq("ui.change"))
        # Mutating this property sets up the UI as well
        self.input_mode = "default"
        return self.frame

    def show_keymap(self, e):
        kbmaps = self.resolve_input_map()
        output = ["{}: {} ".format(k, v) for (k, v) in kbmaps.items() if not k.startswith("_")]
        self.control_bar.set_text(output)

    def resolve_input_map(self):
        mode = self.input_mode
        master = False
        m = self.KEY_MAP.get(mode)
        kbmap = collections.ChainMap(m)
        if m:
            kbmap = kbmap.new_child(m)
            if m.get("_master", False) is True:
                master = True
        if not m and mode != "default" and not master:
            kbmap = kbmap.new_child(self.KEY_MAP["default"])
        return kbmap

    def resolve_input(self, ch):
        kbmap = self.resolve_input_map()
        if ch in kbmap:
            return kbmap[ch]
        return None

    def keypress(self, size, ch):
        action = self.resolve_input(ch)
        if not action:
            return False
        method = None
        method_name = self.UI_ACTIONS.get(action)
        if method_name:
            log.debug("Resolving method %s for %s", method_name, ch)
            method = getattr(self, method_name, None)
        if not method:
            log.debug("Key %s in mapping %s fail to find action %s",
                      ch, self.mode, action)
            return False

        r = method(ch)
        return r is not False

    def quitter(self, ch):
        self.running = False
        self.bus.shutdown()

    async def watch_juju_status(self):
        while self.running:
            p = await asyncio.create_subprocess_shell(
                    "juju status --color=false",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={"PATH": os.environ.get("PATH"),
                         "HOME": os.environ.get("HOME")}
                    )
            stdout, stderr = await p.communicate()
            output = stdout.decode('utf-8')
            self.model.m.clear()
            self.model.m.extend(output.splitlines())
            self.model._modified()
            await asyncio.sleep(2.0)

    async def debug_juju_log(self):
        p = await asyncio.create_subprocess_shell(
                    "juju debug-log --color=false --tail",
                    stdout=asyncio.subprocess.PIPE,
                    env={"PATH": os.environ.get("PATH"),
                         "HOME": os.environ.get("HOME")}
                    )
        while self.running and not p.returncode:
            data = await p.stdout.readline()
            output = data.decode('utf-8').rstrip()
            self.debug.update(output, -1)
        if not p.returncode:
            p.kill()

    def handle_tests(self, e):
        name = ""
        if e.kind == "test.schedule":
            # we can set the progress bar up
            for t in e.payload:
                self.tests[t.name] = {
                        "test": t,
                        "result": "pending",
                        "start": e.time,
                        "stop": 0}
        elif e.kind == "test.start":
            # indicate running
            name = e.payload.name
            self.tests[name]["result"] = "running"
            self.add_log(
                "Starting Test: %s %s" % (name, e.payload.description))
            self.add_log("=" * 78)
            self.test_walker.set_focus(name)
        elif e.kind == "test.complete":
            name = e.payload['test'].name
            self.tests[name]["result"] = e.payload['result']
            self.tests[name]["stop"] = e.time
            self.add_log("-" * 78)
            self.tasks.clear()
        elif e.kind == "test.finish":
            pass

        self.test_walker._modified()

    def toggle_timeline(self, ch):
        if self.frame.body is self.pile:
            self.frame.body = urwid.LineBox(self.timeline, "Timeline")
        else:
            self.frame.body = self.pile

    def populate_timeline(self, e):
        self.timeline.update(str(e.payload))

    def add_log(self, msg):
        self.status.update(msg)

    def show_log(self, event):
        self.add_log(event.payload)

    def show_rule_state(self, event):
        t = event.payload
        rule = t['rule']
        d = self.tasks.setdefault(rule.name, {})
        d.update(t)
        self.task_walker.set_focus(len(self.tasks) - 1)

    def show_state_change(self, event):
        sc = event.payload
        if sc["name"] in self.tasks:
            self.tasks[sc["name"]]["state"] = sc["new_value"]
            self.task_walker._modified()


class RawView(View):
    def subscribe(self):
        self.results = {}
        self.bus.subscribe(self.show_log, eq("logging.message"))
        self.bus.subscribe(self.show_test, prefixed("test."))

    def show_log(self, e):
        print(e.payload.output)

    def show_test(self, e):
        test = e.payload
        if e.kind == "test.start":
            print("Start Test", test.name, test.description)
            print("=" * 78)
        elif e.kind == "test.complete":
            self.results[test['test'].name] = test['result']
            print("-" * 78)
        elif e.kind == "test.finish":
            print("Run Complete")
            context = e.payload
            for test in context.suite:
                print("{:18} {}".format(
                    test.name, TEST_SYMBOLS[self.results[test.name]][1]))
            self.bus.shutdown()


class XUnitView(View):
    def __init__(self, bus, filename):
        self.filename = filename
        self.results = []
        self.current_test = None
        super().__init__(bus)

    def subscribe(self):
        self.bus.subscribe(self.start_test, eq("test.start"))
        self.bus.subscribe(self.record_output, eq("logging.message"))
        self.bus.subscribe(self.record_result, eq("test.complete"))
        self.bus.subscribe(self.write_report, eq("test.finish"))

    def start_test(self, e):
        test = e.payload
        deploy_entity = None
        for rule in test.rules:
            if rule.action.command.endswith('.deploy'):
                deploy_entity = rule.action.args['entity']
        self.current_test = {
            "name": "{}: {}".format(deploy_entity, test.name),
            "result": None,
            "output": [],
            "errors": [],
            "start_time": time(),
        }

    def record_output(self, e):
        if self.current_test:
            self.current_test["output"].append(e.payload.output)
            if e.payload.levelname == "ERROR":
                self.current_test["errors"].append(e.payload.output)

    def record_result(self, e):
        self.current_test["result"] = e.payload["result"]
        self.current_test["end_time"] = time()
        self.results.append(self.current_test)

    def write_report(self, e):
        top = Element("testsuites")
        testsuite = SubElement(top, "testsuite", {
            "name": "matrix",
            "tests": str(len(self.results)),
            "failures": str(len([r for r in self.results if not r["result"]])),
        })
        for test in self.results:
            testcase = SubElement(testsuite, "testcase", {
                "name": test["name"],
                "time": str(test["end_time"] - test["start_time"]),
            })
            if not test["result"]:
                errorelement = SubElement(testcase, "failure", {
                    "message": "\n".join(test["errors"]),
                })
                errorelement.text = "\n".join(test["output"])

        with open(self.filename, "wb") as fp:
            fp.write(tostring(top, encoding="utf-8"))


class NoopViewController:
    def start(self):
        pass

    def stop(self):
        pass
