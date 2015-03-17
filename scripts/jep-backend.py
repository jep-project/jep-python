"""Start script for JEP backend service."""
import logging
import logging.config
import sys
from jep.backend import Backend


def main():
    backend = Backend()
    backend.start()


def _configure_logging():
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'simple': {
                'format': '%(asctime)s %(name)s %(levelname)s: %(message)s'
            }
        },
        'handlers': {
            'console': {
                'stream': sys.stdout,
                'class': 'logging.StreamHandler',
                'formatter': 'simple'
            }
        },
        'loggers': {
            'jep': {
                'handlers': ['console'],
                'propagate': False,
                'level': 'DEBUG'
            },
            '__main__': {
                'handlers': ['console'],
                'propagate': False,
                'level': 'DEBUG'
            }
        },
        'root': {
            'level': 'WARNING',
            'handlers': ['console']
        }
    })


if __name__ == '__main__':
    _configure_logging()
    main()

