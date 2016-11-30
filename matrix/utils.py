import atexit
import copy
import logging
import importlib
import os
import re
import shutil
import tempfile
import zipfile

import aiohttp
import aiofiles


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


def deepmerge(dest, src, merge_lists=False):
    """
    Deep merge of two dicts.

    This is destructive (`dest` is modified), but values
    from `src` are passed through `copy.deepcopy`.
    """
    for k, v in src.items():
        if isinstance(v, dict):
            deepmerge(dest.setdefault(k, {}), v)
        elif isinstance(v, list) and merge_lists:
            dest.setdefault(k, []).extend(copy.deepcopy(vv) for vv in v)
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


async def download_and_extract(archive_url, loop):
    tmpdir = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, tmpdir)
    archive_path = os.path.join(tmpdir, 'archive.zip')
    async with aiofiles.open(archive_path, 'wb') as fb:
        async with aiohttp.ClientSession(loop=loop) as session:
            async with session.get(archive_url) as resp:
                async for data in resp.content.iter_chunked(1024):
                    if data:
                        await fb.write(data)
    with zipfile.ZipFile(archive_path, "r") as z:
        await loop.run_in_executor(z.extractall, tmpdir)
        charmdir = os.commonpath(z.namelist())
    os.unlink(archive_path)
    return charmdir
