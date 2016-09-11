import copy
import json
import logging
import re
import sys
import textwrap

import blessings
import pkg_resources
from pathlib import Path

_marker = object()


def _resolve(name):
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


def freeze(o):
    if isinstance(o, dict):
        return frozenset({k: freeze(v) for k, v in o.items()}.items())

    if isinstance(o, list):
        return tuple([freeze(v) for v in o])

    return o


def make_hash(o):
    return hash(freeze(o))


def nested_get(dict, path, default=None, sep="."):
    o = dict
    for part in path.split(sep):
        if part not in o:
            return default
        o = o[part]
    return o


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


def serialized(obj):
    if hasattr(obj, 'serialized'):
        return obj.serialized()
    return obj


def dump(o, newline=True):
    output = json.dumps(o, indent=2, sort_keys=True, default=serialized)
    if newline and not output.endswith("\n"):
        output = "%s\n" % output
    return output


def path_get(data, path, default=_marker, sep="."):
    o = data
    parts = path.split(sep)
    while parts:
        k = parts.pop(0)
        o = o.get(k, default)
        if o is default:
            break
    if o is _marker:
        raise KeyError(path)
    return o


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
    def __init__(self, terminal, *args, **kwargs):
        self.highlights = kwargs.pop("highlights", {})
        self.line_levels = kwargs.pop("line_levels", True)
        self.pretty = kwargs.pop("pretty", True)
        self.pat = None
        self.regex = None
        if self.highlights:
            keys = self.highlights.keys()
            self.pat = "({})(\W)".format(
                "|".join(keys)
            )
            self.regex = re.compile(self.pat, re.M | re.I)

        super(HighlightFormatter, self).__init__(*args, **kwargs)
        self._terminal = terminal

    def format(self, record):
        # Add the terminal to the formatter allowing
        # standard blessing.py syntax in the format
        record.terminal = self._terminal.term
        output = super(HighlightFormatter, self).format(record)
        if self.regex:
            def highlight(match):
                scheme = getattr(self._terminal,
                                 self.highlights[match.group(1).lower()])
                return scheme(match.group(1)) + match.group(2)

            output = self.regex.sub(highlight, output)
        if self.line_levels:
            if record.levelno >= logging.CRITICAL:
                line_color = self._terminal.bold_yellow_on_red
            elif record.levelno >= logging.ERROR:
                line_color = self._terminal.red
            elif record.levelno >= logging.WARNING:
                line_color = self._terminal.yellow
            elif record.levelno >= logging.INFO:
                line_color = self._terminal.green
            else:
                line_color = self._terminal.white
            return line_color(output)
        if self.pretty:
            textwrap.fill(output, width=70, break_long_words=False)

        return output


class TermWriter(object):
    def __init__(self, fp=None, term=None, force_styling=False):
        if fp is None:
            fp = sys.stdout
        self.fp = fp
        if term is None:
            term = blessings.Terminal(force_styling=force_styling)
        self.term = term

    def __getattr__(self, key):
        return getattr(self.term, key)

    def write(self, msg,  *args, **kwargs):
        if 't' in kwargs:
            raise ValueError("Using reserved token 't' in TermWriter.write")
        kwargs['t'] = self.term
        self.fp.write(msg.format(*args, **kwargs))


def load_schema(package, schema):
    fn = Path(pkg_resources.resource_filename(package, schema + ".schema"))
    return json.loads(fn.text(), encoding="utf-8")
