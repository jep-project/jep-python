import logging
import logging.config
import sys
from jep.frontend import Frontend, BackendListener, State
from jep.schema import Shutdown

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

_logger = logging.getLogger('jep.frontend.sample')


class MyListener(BackendListener):
    def on_backend_alive(self, context):
        #context.send_message(Shutdown())
        context.disconnect()
        pass


frontend = Frontend([MyListener()])
connection = frontend.provide_connection('localfile.mydsl')

while connection.state is not State.Disconnected:
    connection.run(1)