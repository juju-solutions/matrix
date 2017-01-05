import asyncio
import argparse
import logging
import logging.config
from pathlib import Path
from pkg_resources import resource_filename
import sys

from .bus import Bus, set_default_bus
from . import config
from . import rules
from . import utils


def configLogging(options):
    logging.captureWarnings(True)
    if options.output_dir:
        # Set output dir for log.
        config.LoggingConfig['handlers']['file']['filename'] = str(Path(
            options.output_dir,
            config.LoggingConfig['handlers']['file']['filename']))

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
    parser = argparse.ArgumentParser(
        formatter_class=utils.ParagraphDescriptionFormatter,
        description="Run a local bundle through a suite of tests to ensure "
                    "that it can handle the types of operations and failures "
                    "that are common for all deployments.",
        epilog="A default suite of tests will always be run, unless -D "
               "is given.  Additional suites can be passed in as "
               "arguments.  Additionally, the bundle will be checked for "
               "a tests/matrix.yaml file which will be included as an "
               "additional suite if present.  All suites will be merged "
               "together, and suites containing tests with the same name as a "
               "test in a previous suite will override that test.\n"
               "\n"
               "Examples:\n"
               "\n"
               "    Run all normal tests (default suite and, if present, "
               "./tests/matrix.yaml) on the bundle at ./:\n"
               "\n"
               "        $ matrix\n"
               "\n"
               "    Run only the default suite (ignore ./tests/matrix.yaml):\n"
               "\n"
               "        $ matrix -B\n"
               "\n"
               "    Run all normal tests on the bundle at ~/foo:\n"
               "\n"
               "        $ matrix -p ~/foo\n"
               "\n"
               "    Run only ~/foo/tests/matrix.yaml on the bundle at ~/foo:\n"
               "\n"
               "        $ matrix -Dp ~/foo\n"
               "\n"
               "    Run all normal tests plus ./tests/matrix_extra.yaml on "
               "the bundle at ./:\n"
               "\n"
               "        $ matrix tests/matrix_extra.yaml\n"
               "\n"
               "    Run only ./tests/matrix_extra.yaml:\n"
               "\n"
               "        $ matrix -DB tests/matrix_extra.yaml\n"
               "\n",
    )
    parser.add_argument("-c", "--controller", default=None,
                        help="Controller to use (default: current)")
    parser.add_argument("-m", "--model", default=None,
                        help="Model to use instead of creating one per test")
    parser.add_argument("-k", "--keep-models", action="store_true",
                        default=False, help="Keep the created per-test models "
                                            "for further inspection")
    parser.add_argument("-l", "--log-level", default=None,
                        help="Set log level.")
    parser.add_argument("-L", "--log-name", nargs="*",
                        help="If specified, log-level param will only "
                             "apply to the named internal log.")
    parser.add_argument("-f", "--log-filter", nargs="*",
                        help="Specify a custom log filter.")
    parser.add_argument("-d", "--output-dir", default=None,
                        help="Directory that should contain logs, "
                             "glitch plans, and other artifacts. Defaults "
                             "to the current working dir.")
    parser.add_argument("-s", "--skin", choices=("tui", "raw"), default="tui")
    parser.add_argument("-x", "--xunit", default=None, metavar='FILENAME',
                        help="Create an XUnit report file")
    parser.add_argument("-F", "--fail-fast", action="store_true")
    parser.add_argument("-i", "--interval", default=5.0, type=float)
    parser.add_argument("-p", "--path", default=Path.cwd(), type=Path,
                        help="Path to local bundle to test "
                             "(defaults to current directory)")
    parser.add_argument("-D", "--no-default-suite", dest="default_suite",
                        default=resource_filename(__name__, "matrix.yaml"),
                        action="store_false", help="Do not include the default"
                                                   " suite as the first suite")
    parser.add_argument("-B", "--no-bundle-suite", dest="bundle_suite",
                        default="tests/matrix.yaml", action="store_false",
                        help="Do not include the suite provided by the bundle")
    parser.add_argument("additional_suites", nargs="*",
                        help="Additional suites to be merged with the "
                             "default suite before running")
    parser.add_argument("-t", "--test_pattern", nargs="*", default=["*"],
                        help="Pattern for selecting which tests "
                             "from the suite(s) are run")
    parser.add_argument("-g", "--glitch_plan")
    parser.add_argument("-n", "--glitch_num", default=5)
    parser.add_argument("-o", "--glitch_output", default="glitch_plan.yaml")
    options = parser.parse_args(args, namespace=matrix)
    if not (options.path.is_dir() and (options.path / 'bundle.yaml').exists()):
        parser.error('Invalid bundle directory: %s' % options.path)

    configLogging(options)
    return options


def main(args=None):
    loop = asyncio.get_event_loop()
    bus = Bus(loop=loop)
    # logging resolves default bus from the module
    set_default_bus(bus)

    matrix = rules.RuleEngine(bus=bus)
    options = setup(matrix, args)
    loop.set_debug(options.log_level == logging.DEBUG)

    try:
        loop.create_task(matrix())
        loop.run_forever()
    finally:
        loop.close()
        if matrix.exit_code:
            sys.exit(matrix.exit_code)
