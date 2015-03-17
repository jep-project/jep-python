"""Framework independent PEP backend implementation."""
import enum
import logging
import logging.config
import socket
import sys
import select
from jep.protocol import JepProtocolListener, MessageSerializer

_logger = logging.getLogger(__name__)

#: Range to search for available ports.
PORT_RANGE = (9001, 9100)

#: Length of server's listen queue.
LISTEN_QUEUE_LENGTH = 3

#: Data buffer length in bytes.
BUFFER_LENGTH = 10000

#: Number of seconds between backend alive messages.
PERIOD_BACKEND_ALIVE_SEC = 1


class NoPortFoundError(Exception):
    pass


@enum.unique
class State(enum.Enum):
    Stopped = 1
    Running = 2
    ShutdownPending = 3


class Backend():
    def __init__(self, listeners=None, serializer=None):
        self.serversocket = None
        self.state = State.Stopped
        self.serializer = serializer or MessageSerializer()
        self.listeners = listeners or []

    def start(self):
        """Starts listening for front-ends to connect."""

        _logger.debug('Starting backend.')
        self._listen()
        self._run()

    def _listen(self):
        """Set up server socket to listen for incoming connections."""
        # find available port to listen:
        self.serversocket = socket.socket()
        port = PORT_RANGE[0]
        while self.state is not State.Running and port < PORT_RANGE[1]:
            try:
                self.serversocket.bind(('localhost', port))
                self.serversocket.listen(LISTEN_QUEUE_LENGTH)
                self.state = State.Running
            except OSError:
                _logger.debug('Port %d not available.' % port)
                port += 1
        if self.state is not State.Running:
            _logger.error('Could not bind to any available port in range [%d,%d]. Startup failed.' % PORT_RANGE)
            raise NoPortFoundError()
        print('JEP service, listening on port %d' % port)

    def _run(self):
        """Process connections and messages. This is the main loop of the server."""

        sockets = [self.serversocket]
        while self.state is State.Running:
            readable, *_ = select.select(sockets, [], [], 1)
            _logger.debug('Readable sockets: %d' % len(readable))

            for rsocket in readable:
                if rsocket is self.serversocket:
                    sockets.append(self._accept())
                else:
                    self._receive(rsocket)

    def _accept(self):
        """Blocking accept of incoming connection."""
        clientsocket, *_ = self.serversocket.accept()
        _logger.info('Frontend connected.')
        return clientsocket

    def _receive(self, clientsocket):
        """Blocking read of client data on given socket."""
        data = clientsocket.recv(BUFFER_LENGTH)
        _logger.debug('Received data: %s' % data)
        msg = self.serializer.deserialize(data)
        _logger.debug('Received message: %s' % msg)

        map(lambda l: l.on_message_received(msg), self.listeners)


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
