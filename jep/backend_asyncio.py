"""JEP backend support on top of asyncio."""
import asyncio
import logging
import logging.config
import sys
from jep.backend import Backend, PORT_RANGE, PERIOD_BACKEND_ALIVE_SEC, BackendState
from jep.protocol_asyncio import JepProtocol

_logger = logging.getLogger(__name__)

# TODO: Some of the functionality below should be refactored into framework independent code.


class AsyncioBackend(Backend):
    def __init__(self, loop=None):
        super().__init__()
        self.loop = loop or asyncio.get_event_loop()
        self.server = None

    @asyncio.coroutine
    def run(self):
        # TODO: implement port search if port is not available, possibly in a generic way.
        port = PORT_RANGE[0]
        _logger.info('Asyncio JEP backend starting - Welcome.')
        self.server = yield from self.loop.create_server(self._protocol_factory, 'localhost', port)

        print('JEP service, listening on port %d.\n' % port)
        self.state = BackendState.Listening
        while (self.state < BackendState.ShutdownPending):
            if self.state==BackendState.Connected:
                self.protocol.send_message(BackendAlive)
            yield from asyncio.sleep(PERIOD_BACKEND_ALIVE_SEC)

        _logger.info('Asyncio JEP backend shutting down.')
        self.server.close()
        self.loop.run_until_complete(self.server.wait_closed())

    def _protocol_factory(self):
        """Create protocol with registered backend to listen for events."""
        return JepProtocol(listener=self)


def main():
    loop = asyncio.get_event_loop()
    backend = AsyncioBackend(loop)
    loop.run_until_complete(backend.run())


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
    # if started this way, use default logging configuration:
    _configure_logging()
    main()