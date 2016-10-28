import asyncio
import argparse
import logging
import logging.config
from pathlib import Path

import urwid

from .bus import Bus, set_default_bus
from . import config
from . import rules
from .view import TUIView, RawView, NoopViewController, palette


def configLogging(options):
    logging.captureWarnings(True)
    logging.config.dictConfig(config.LoggingConfig)

    root_logger = logging.getLogger()
    if isinstance(options.log_level, str):
        options.log_level = options.log_level.upper()
    if options.log_level is not None:
        for loggerName in config.LoggingConfig["loggers"]:
            logger = logging.getLogger(loggerName)
            if options.log_name and loggerName not in options.log_name:
                logger.setLevel(logging.CRITICAL)
            else:
                logger.setLevel(options.log_level)
        root_logger.setLevel(options.log_level)

    if options.log_filter:
        fil = root_logger.handlers[0].filters[0]
        fil.update_selections(options.log_filter)


def setup(matrix, args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--log-level", default=None)
    parser.add_argument("-L", "--log-name", nargs="*")
    parser.add_argument("-f", "--log-filter", nargs="*")
    parser.add_argument("-s", "--skin", choices=("tui", "raw"), default="tui")
    parser.add_argument("-i", "--interval", default=5.0, type=float)
    parser.add_argument("-p", "--path", default=Path.cwd() / "tests",
                        type=Path)
    parser.add_argument("config_file", type=open)
    parser.add_argument("test_pattern", nargs="*", default=["*"])
    options = parser.parse_args(args, namespace=matrix)

    configLogging(options)
    return options


def unhandled(key):
    if key == "ctrl c":
        raise urwid.ExitMainLoop()


def main(args=None):
    loop = asyncio.get_event_loop()
    bus = Bus(loop=loop)
    # logging resolves default bus from the module
    set_default_bus(bus)

    matrix = rules.RuleEngine(bus=bus)
    options = setup(matrix, args)
    loop.set_debug(options.log_level == logging.DEBUG)

    if options.skin == "tui":
        screen = urwid.raw_display.Screen()
        view = TUIView(bus, screen)
        view_controller = urwid.MainLoop(
            view.widgets,
            palette,
            screen=screen,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
            unhandled_input=unhandled)
    else:
        view = RawView(bus)
        view_controller = NoopViewController()

    try:
        view_controller.start()
        loop.create_task(matrix())
        loop.run_forever()
    finally:
        view_controller.stop()
        loop.close()
