"""Start script for JEP backend service."""
import sys

try:
    import jep as jeptestimport
except ImportError:
    # not in path, do it now:
    import os.path
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import logging
import logging.config
from jep.backend import Backend, FrontendListener

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

_logger = logging.getLogger('jep.backend.sample')


class Listener(FrontendListener):
    def on_shutdown(self, context):
        _logger.info('Received shutdown in listener.')


Backend([Listener()]).start()
