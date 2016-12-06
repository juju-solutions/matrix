import argparse
import copy
import logging
import importlib
import re
import textwrap

import urwid


_marker = object()


def resolve_dotpath(name):
    """Resolve a dotted name to a global object."""
    modules = name.split('.')
    attrs = [modules.pop()]
    module = None
    while modules:
        try:
            module = importlib.import_module('.'.join(modules))
            break
        except ImportError:
            attrs.insert(0, modules.pop())
    else:
        raise ImportError('Unable to find %s' % name)
    found = module
    for attr in attrs:
        found = getattr(found, attr)
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


def merge_spec(old_spec, new_spec):
    """
    Merge a test suite spec by merging the list of tests.

    The tests will be merged by name; if ``new_spec`` contains a test with
    the same name as ``old_spec``, the test from ``new_spec`` will be used
    instead.

    Note that this is destructive, so ``old_spec`` will be modified in place.
    """
    old_by_name = {test['name']: test
                   for test in old_spec['tests']
                   if 'name' in test}
    for new_test in new_spec['tests']:
        if 'name' in new_test and new_test['name'] in old_by_name:
            # test case exists in both (by name), so replace it
            old_test = old_by_name[new_test['name']]
            old_test.clear()
            old_test.update(copy.deepcopy(new_test))
        else:
            # new test case, so add it
            old_spec['tests'].append(new_test)


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


class ParagraphDescriptionFormatter(argparse.HelpFormatter):
    def _fill_text(self, text, width, indent):
        lines = []
        for line in text.splitlines():
            if line.strip():
                current_indent = indent
                additional_indent = re.match(r'(\s+)(.*)', line)
                if additional_indent:
                    current_indent += additional_indent.group(1)
                    line = additional_indent.group(2)
                lines.extend(textwrap.wrap(line, width,
                                           initial_indent=current_indent,
                                           subsequent_indent=current_indent))
            else:
                lines.append(line)  # preserve blank lines
        return '\n'.join(lines)


def translate_ansi_colors(entity):
    if not entity:
        return entity
    colors = ['black',
              'dark red',
              'dark green',
              'brown',
              'dark blue',
              'dark magenta',
              'dark cyan',
              'light gray',
              'dark gray',
              'light red',
              'light green',
              'yellow',
              'light blue',
              'light magenta',
              'light cyan',
              'white']
    results = []
    split_pat = re.compile('(\x1b\[[^m]+m[^\x1b]*)\x1b\[0m')
    parse_pat = re.compile('\x1b\[([^m]+)m(.*)')
    for part in split_pat.split(entity):
        match = parse_pat.match(part)
        if match:
            color_code, text = match.groups()
            fg = []
            bg = 'default'
            for code in color_code.split(';'):
                code = int(code)
                if code == 1:
                    fg.append('bold')
                elif 30 <= code <= 37:
                    fg.append(colors[code-30])
                elif 40 <= code <= 47:
                    bg = colors[code-40]
                elif 90 <= code <= 97:
                    fg.append('bold')
                    fg.append(colors[code-90])
            part = (urwid.AttrSpec(','.join(fg), bg), text)
        if part:
            results.append(part)
    return results
