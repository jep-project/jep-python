import logging
import logging.config
import sys
import datetime
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
        #context.disconnect()
        pass


frontend = Frontend([MyListener()])
connection = frontend.get_connection('localfile.mydsl')

started = datetime.datetime.now()
cycles = 0
while connection.state is not State.Disconnected:
    connection.run(datetime.timedelta(seconds=0.1))
    cycles += 1
ended = datetime.datetime.now()

_logger.info('Frontend executed %d cycles in %.2f seconds.' % (cycles, (ended - started).total_seconds()))
