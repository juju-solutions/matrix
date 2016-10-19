import collections
import logging

import urwid

log = logging.getLogger("view")

palette = [
        ("default", "white", "black"),
        ("header", "white", "black", "standout"),
        ("pass", "dark green", "black"),
        ("fail", "dark red", "black"),
        ("focused", "black", "dark cyan", "standout")
        ]


class View:
    def __init__(self, bus):
        self.bus = bus
        self.build_ui()
        self.subscribe()

    def build_ui(self):
        pass

    def subscribe(self):
        pass


class BufferedList(collections.deque):
    def __init__(self, limit):
        seed = ["\n"] * limit
        super(BufferedList, self).__init__(seed, limit)

    def render(self):
        return "\n".join(self)


class BufferedDict(collections.OrderedDict):
    def __init__(self, limit):
        self.limit = limit
        super(BufferedDict, self).__init__()

    def render(self, row_func):
        output = collections.deque([""] * self.limit, self.limit)
        for v in self.values():
            output.append(row_func(v))
        return "\n".join(output)


class SelectableText(urwid.Edit):
    def valid_char(self, ch):
        return False


def render_row(row):
    return "{:18} -> {}".format(row["name"], row.get("state", "pending"))


class TUIView(View):
    def build_ui(self):
        self.tasks = urwid.Text("")
        self.task_view = BufferedDict(6)
        self.status = urwid.Text("")
        self.status_view = BufferedList(10)
        self.run_ct = 0
        self.results = []

        self.pile = urwid.Pile([
                    urwid.Text(("header", "Matrix")),
                    urwid.Divider(),
                    urwid.LineBox(self.tasks),
                    urwid.LineBox(self.status),
                    ])
        self.widgets = urwid.Filler(
                self.pile,
                'top', min_height=5)

    def subscribe(self):
        def is_log(e):
            return e.kind == "logging.message"

        def is_rule(e):
            return e.kind.startswith("rule.")

        def is_state(e):
            return e.kind.startswith("state.")

        def is_test(e):
            return e.kind.startswith("test.")

        self.bus.subscribe(self.show_log, is_log)
        self.bus.subscribe(self.show_rule_state, is_rule)
        self.bus.subscribe(self.show_state, is_state)
        self.bus.subscribe(self.handle_tests, is_test)

    def handle_tests(self, e):
        name = ""
        if e.kind == "test.schedule":
            # we can set the progress bar up
            self.run_total = len(e.payload)
            self.progress = urwid.Text("")
            self.pile.contents.insert(2, (self.progress, self.pile.options()))
        elif e.kind == "test.start":
            # indicate running
            name = e.payload.name
            self.add_log("Starting Test: %s" % name)
        elif e.kind == "test.complete":
            # status symbol
            self.run_ct += 1
            self.results.append(e.payload.result)

        symbol = {True: ("pass", "✓"), False: ("fail", "✕")}
        output = ["{}/{} ".format(self.run_ct, self.run_total)]
        output.extend([symbol[r] for r in self.results])
        output.append(" {}".format(name))
        self.progress.set_text(output)

        if e.kind == "test.finish":
            self.show_timeline(e)

    def show_timeline(self, e):
        p = self.pile
        context = e.payload
        events = []
        # remove status/task widgets
        p.contents = p.contents[:3]
        for evt in context.timeline:
            tl = SelectableText(str(evt))
            tl = urwid.AttrMap(tl, None, "focused")
            events.append(tl)

        def quit_handler(edit, new_text):
            if new_text.lower() == "q":
                self.bus.shutdown()

        quitter = urwid.Edit("Press 'q' to exit... ", multiline=False)
        events.append(quitter)
        urwid.connect_signal(quitter, "change", quit_handler)

        body = urwid.SimpleFocusListWalker(events)
        listbox = urwid.ListBox(body)
        ba = urwid.BoxAdapter(listbox, 20)
        p.contents.append((ba, p.options()))
        listbox.focus_position = len(body) - 1
        self.pile.focus_position = len(self.pile.contents) - 1

    def add_log(self, msg):
        self.status_view.append(msg)
        self.status.set_text(self.status_view.render())

    def show_log(self, event):
        self.add_log(event.payload.output)

    def show_rule_state(self, event):
        t = event.payload
        self.task_view.setdefault(t['name'], {}).update(t)
        self.tasks.set_text(self.task_view.render(render_row))

    def show_state(self, event):
        if event.kind != "state.change":
            return
        sc = event.payload
        self.task_view[sc['name']]['state'] = sc['new_value']
        self.tasks.set_text(self.task_view.render(render_row))


class RawView(View):
    def subscribe(self):
        self.bus.subscribe(
                self.show_log,
                lambda e: e.kind == "logging.message")

        def is_test(e):
            return e.kind.startswith("test")

        self.bus.subscribe(self.show_test, is_test)

    def show_log(self, e):
        print(e.payload.output)

    def show_test(self, e):
        test = e.payload
        if e.kind == "test.start":
            print("Start Test", test.name, test.description)
            print("=" * 78)
        elif e.kind == "test.complete":
            print("Test Complete", test.name, test.result)
            print("-" * 78)
        elif e.kind == "test.finish":
            self.show_results(e.payload)

    def show_results(self, context):
        print("Run Complete")
        symbol = {True: "✓", False: "✕"}
        for test in context.suite:
            print("{:18} {}".format(test.name, symbol[test.result]))
        self.bus.shutdown()


class NoopViewController:
    def start(self):
        pass

    def stop(self):
        pass
