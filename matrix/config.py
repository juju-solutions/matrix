LoggingConfig = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "()": "matrix.utils.HighlightFormatter",
            "format": "{name}:{lineno}:{funcName}: {message}",  # noqa
            "style": "{",
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
            "()": "matrix.utils.EventHandler",
            "formatter": "standard",
            "bus": "ext://matrix.bus.default_bus",
            "filters": ["default"],
        },
        "file": {
            "()": "logging.FileHandler",
            "filename": "matrix.log",
            "mode": "w",
            "formatter": "standard",
            "filters": ["default"],
            }
    },
    "loggers": {
        "": {
            "handlers": ["default", "file"],
            "level": "INFO",
            "propagate": False,
        },

        "asyncio": {
            "handlers": ["default", "file"],
            "level": "INFO",
            "propagate": False
        },

        "bus": {
            "handlers": ["file"],
            "level": "DEBUG",
            "propagate": False
            },

        "requests.packages.urllib3": {
            "handlers": ["default"],
            "level": "WARN",
            "propagate": False
            },

       "websockets": {
            "handlers": ["default"],
            "level": "WARN",
            "propagate": False
            },

   }
}
