LoggingConfig = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{name}:{lineno}:{funcName}: {message}",  # noqa
            "style": "{",
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
            "level": "INFO",
            "propagate": False
            },

        "juju.model": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": False
            },

        "requests.packages.urllib3": {
            "handlers": ["file"],
            "level": "WARN",
            "propagate": False
            },

        "websocket": {
            "handlers": ["file"],
            "level": "WARN",
            "propagate": False
            },

       "websockets": {
            "handlers": ["file"],
            "level": "WARN",
            "propagate": False
            },

       "websockets.protocol": {
            "handlers": ["file"],
            "level": "WARN",
            "propagate": False
            },


   }
}
