import copy
import logging
import importlib
import re


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
