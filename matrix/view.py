import asyncio
import collections
import datetime
import logging
from time import time
from xml.etree.ElementTree import Element, SubElement, tostring

import urwid

from .model import PENDING

log = logging.getLogger("view")

palette = [
        ("default", "default", "default"),
        ("header", "white", "default", "standout"),
        ("pass", "dark green", "default"),
        ("fail", "dark red", "default"),
        ("focused", "black", "dark cyan", "standout"),
        ("DEBUG", "dark cyan", "default"),
        ("INFO", "default", "default"),
        ("WARNING", "yellow", "default"),
        ("ERROR", "dark red", "default"),
        ("CRITICAL", "dark red", "default"),
        ]


TEST_SYMBOLS = {
        True: ("pass", "\N{HEAVY CHECK MARK}"),
        False: ("fail", "\N{HEAVY BALLOT X}"),
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


class View:
    def __init__(self, bus, screen=None):
        self.bus = bus
        self.screen = screen
        self.widgets = self.build_ui()
        self.subscribe()

    def build_ui(self):
        pass

    def subscribe(self):
        pass


class SelectableText(urwid.Edit):
    def valid_char(self, ch):
        return False


class ControlBar(urwid.Edit):
    def configure(self, mapping):
        self.callback_map = mapping
        return self

    def keypress(self, size, ch):
        if ch in self.callback_map:
            m, ctx, args = self.callback_map[ch]
            m(ctx, *args)
            return
        return ch


def eq(expected):
    def _eq(e):
        return e.kind == expected
    return _eq


def prefixed(expected):
    def _prefixed(e):
        return e.kind.startswith(expected)
    return _prefixed


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


class TUIView(View):
    def build_ui(self):
        widgets = []

        def fetch_name(obj):
            return obj['test'].name

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

        self.status = collections.deque([], 100)
        self.status_walker = SimpleListRenderWalker(
                self.status, widget_func=render_status)
        self.status_view = urwid.ListBox(self.status_walker)
        self.bus.subscribe(self.show_log, eq("logging.message"))

        self.running = True
        self.model_view = urwid.Terminal(['watch', '--color', '--',
                                          'juju', 'status', '--color=true'])

        self.debug_view = urwid.Terminal(['juju', 'debug-log',
                                          '--color=true', '--tail'])

        widgets.append(("weight", 2, urwid.Columns([
            urwid.LineBox(self.status_view, "Status Log"),
            urwid.Pile([
                urwid.LineBox(self.model_view, "Juju Model"),
                ("weight", 0.6, urwid.LineBox(self.debug_view, "Juju Debug")),
                ])
            ])))

        self.pile = body = urwid.Pile(widgets)
        self.frame = urwid.Frame(
                header=urwid.Text("Matrix Test Runner"),
                body=body)
        return self.frame

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
        elif e.kind == "test.finish":
            def quit_handler(ctx):
                self.running = False
                ctx.bus.shutdown()

            def timeline_view(ctx, e):
                ctx.show_timeline(e)

            control_bar = ControlBar("t for timeline, q to quit")
            control_bar.configure({
                'q': (quit_handler, self, ()),
                't': (timeline_view, self, (e,)),
                })
            self.frame.footer = control_bar
            self.frame.focus_position = "footer"
        self.test_walker._modified()

    def show_timeline(self, e):
        context = e.payload
        events = []
        # remove status/task widgets
        for evt in context.timeline:
            tl = SelectableText(str(evt))
            tl = urwid.AttrMap(tl, None, "focused")
            events.append(tl)

        def quit_handler(edit, new_text):
            if new_text.lower() == "q":
                self.running = False
                self.bus.shutdown()

        quitter = urwid.Edit("Press 'q' to exit... ", multiline=False)
        urwid.connect_signal(quitter, "change", quit_handler)
        events.append(quitter)

        body = urwid.SimpleFocusListWalker(events)
        listbox = urwid.TreeListBox(body)
        self.frame.body = urwid.LineBox(listbox, "Timeline")
        self.frame.focus_position = "body"
        listbox.focus_position = len(body) - 1

    def add_log(self, msg):
        self.status_walker.update(msg)

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
