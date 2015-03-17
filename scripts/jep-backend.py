"""Start script for JEP backend service."""
import logging
import logging.config
import sys
from jep.backend import Backend

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
        }
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['console']
    }
})

Backend().start()
