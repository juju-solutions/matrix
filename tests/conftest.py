import pytest  # noqa


def pytest_addoption(parser):
    parser.addoption("--controller", default=None,
                     help="controller to use for full-stack test")
