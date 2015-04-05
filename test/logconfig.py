import logging.config
import sys

__author__ = 'mpagel'


def configure_test_logger():
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