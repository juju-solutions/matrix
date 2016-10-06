import builtins
import collections

import attr
import urwid


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


class TUIView(View):
    def build_ui(self):
        self.status = urwid.Text("")
        self.status_view = BufferedList(10)

        self.tasks = urwid.Text("")
        self.task_view = BufferedDict(6)

        self.run_ct = 0
        self.results = []

        self.pile = urwid.Pile([
                    self.tasks,
                    self.status,
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
        if e.kind == "test.schedule":
            # we can set the progress bar up
            self.run_total = len(e.payload)
            self.progress = urwid.Text("")
            self.pile.contents.insert(0, (self.progress, self.pile.options()))
        elif e.kind == "test.started":
            # indicate running
            pass
        elif e.kind == "test.complete":
            # status symbol
            self.run_ct += 1
            self.results.append(e.payload['result'])

        symbol = {True: "✓", False: "✕"}
        self.progress.set_text("{}/{} {}".format(
            self.run_ct,
            self.run_total,
            " ".join([symbol[r] for r in self.results])))

    def show_log(self, event):
        self.status_view.append(event.payload.output)
        self.status.set_text(self.status_view.render())

    def show_rule_state(self, event):
        t = event.payload
        d = attr.asdict(t)
        d['name'] = t.name
        self.task_view[t.name] = d

        def render_row(row):
            return "{:18} pending".format(row["name"])

        self.tasks.set_text(self.task_view.render(render_row))

    def show_state(self, event):
        sc = event.payload
        self.task_view[sc['name']]['state'] = sc['new_value']

        def render_row(row):
            return "{:18} {}".format(row["name"], row["state"])

        self.tasks.set_text(self.task_view.render(render_row))


class RawView(View):
    def subscribe(self):
        self.bus.subscribe(
                self.show_log,
                lambda e: e.kind == "logging.message")

    def show_log(self, e):
        print(e.payload.output)


class NoopViewController:
    def start(self):
        pass

    def stop(self):
        pass
