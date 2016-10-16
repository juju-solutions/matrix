import copy
import logging
import re


_marker = object()


def resolve_dotpath(name):
    """Resolve a dotted name to a global object."""
    name = name.split('.')
    used = name.pop(0)
    found = __import__(used)
    for n in name:
        used = used + '.' + n
        try:
            found = getattr(found, n)
        except AttributeError:
            __import__(used)
            found = getattr(found, n)
    return found


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                    Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def deepmerge(dest, src):
    """
    Deep merge of two dicts.

    This is destructive (`dest` is modified), but values
    from `src` are passed through `copy.deepcopy`.
    """
    for k, v in src.items():
        if dest.get(k) and isinstance(v, dict):
            deepmerge(dest[k], v)
        else:
            dest[k] = copy.deepcopy(v)
    return dest


class O(dict):
    def __getattr__(self, key):
        value = self.get(key, _marker)
        if value is _marker:
            raise AttributeError(key)
        return value


class DynamicFilter(logging.Filter):
    def __init__(self, selections=None):
        self.selections = set()
        self.update_selections(selections)

    def update_selections(self, selections):
        if not selections:
            return
        self.selections = self.selections.union(selections)
        pat = "({})".format(
            "|".join(self.selections)
        )
        self.regex = re.compile(pat, re.M | re.I)

    def filter(self, record):
        if not self.selections:
            return True
        rec = [v for k, v in vars(record).items() if isinstance(v, str)]
        for el in rec:
            if self.regex.search(el):
                return True
        if record.args:
            for obj in record.args:
                if self.regex.search(str(obj)):
                    return True
        return False


class HighlightFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        self.line_levels = kwargs.pop("line_levels", True)
        self.pretty = kwargs.pop("pretty", True)
        super(HighlightFormatter, self).__init__(*args, **kwargs)

    def format(self, record):
        # Add the terminal to the formatter allowing
        # standard blessing.py syntax in the format
        output = super(HighlightFormatter, self).format(record)
        if False and self.line_levels:
            output = ({
                logging.CRITICAL: ("bold yellow", "red"),
                logging.ERROR: ("red", "black"),
                logging.WARNING: ("yellow", "black"),
                logging.INFO: ("green", "black"),
                logging.DEBUG: ""
                }[record.levelno], output)
        return output


class EventHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET, bus=None):
        super(EventHandler, self).__init__(level)
        self.bus = bus

    def emit(self, record):
        try:
            msg = self.format(record)
            record.output = msg
            self.bus.dispatch(
                    origin=record.name,
                    kind="logging.message",
                    payload=record)
        except:
            self.handleError(record)
