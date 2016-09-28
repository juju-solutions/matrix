import asyncio
import argparse
import logging
import logging.config
from pathlib import Path
import sys

from . import config
from . import rules


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
    parser.add_argument("-i", "--interval", default=5.0, type=float)
    parser.add_argument("-p", "--path", default=Path.cwd() / "tests",
                        type=Path)
    parser.add_argument("-r", "--show-report", action="store_true",
                        default=False)
    parser.add_argument("config_file", type=open)
    options = parser.parse_args(args, namespace=matrix)

    configLogging(options)
    return options


def main(args=None):
    matrix = rules.RuleEngine()
    options = setup(matrix, args)
    loop = asyncio.get_event_loop()
    loop.set_debug(options.log_level == logging.DEBUG)
    loop.create_task(matrix())
    try:
        loop.run_forever()
    finally:
        loop.stop()
        loop.close()
