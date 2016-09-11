from . import utils

# Highlights in logging, color scheme work as
# per Python's blessings module
HIGHLIGHTS = {
    "matrix": "bold_green",
    "test": "bold_yellow",
    "fail": "bold_red",
    "error": "bold_red",
}


LoggingConfig = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "()": "matrix.utils.HighlightFormatter",
            "format": "{terminal.bold}{name}:{lineno}:{funcName}{terminal.normal}: {message}",  # noqa
            "style": "{",
            "terminal": utils.TermWriter(),
            "highlights": HIGHLIGHTS,
            "line_levels": True,
        },
    },
    "filters": {
        "default": {
            "()": "matrix.utils.DynamicFilter",
        }
    },
    "handlers": {
        "default": {
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "filters": ["default"],
        },
    },
    "loggers": {
        "": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": True,
        },

        "asyncio": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False
        },
    }
}
