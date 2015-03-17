"""Framework independent PEP backend implementation."""
import enum
import logging
import socket
import select
from jep.protocol import JepProtocolListener, MessageSerializer
from jep.schema import Shutdown

_logger = logging.getLogger(__name__)

#: Range to search for available ports.
PORT_RANGE = (9001, 9100)

#: Length of server's listen queue.
LISTEN_QUEUE_LENGTH = 3

#: Data buffer length in bytes.
BUFFER_LENGTH = 10000

#: Number of seconds between select timeouts.
TIMEOUT_SELECT_SEC = 1

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
    """Synchronous JEP backend service."""

    def __init__(self, listeners=None, serializer=None):
        self.sockets = []
        self.state = State.Stopped
        self.serializer = serializer or MessageSerializer()
        self.listeners = listeners or []

    @property
    def serversocket(self):
        return self.sockets[0] if self.sockets else None

    def start(self):
        """Starts listening for front-ends to connect."""

        _logger.info('Starting backend.')
        self._listen()
        self._run()
        _logger.info('Backend stopped.')

    def _listen(self):
        """Set up server socket to listen for incoming connections."""
        # find available port to listen at:
        self.sockets = [socket.socket()]
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

        while self.state is State.Running:
            readable, *_ = select.select(self.sockets, [], [], TIMEOUT_SELECT_SEC)
            _logger.debug('Readable sockets: %d' % len(readable))

            for sock in readable:
                if sock is self.serversocket:
                    self._accept()
                else:
                    if not self._receive(sock):
                        _logger.info('Closing connection to frontend.')
                        self._close(sock)

        if self.state == State.ShutdownPending:
            map(self._close, self.sockets)
            self.state = State.Stopped

    def _accept(self):
        """Blocking accept of incoming connection."""
        clientsocket, *_ = self.serversocket.accept()
        self.sockets.append(clientsocket)
        _logger.info('Frontend connected.')

    def _receive(self, clientsocket):
        """Blocking read of client data on given socket. Returns flag whether socket is still healthy."""
        data = clientsocket.recv(BUFFER_LENGTH)
        if data:
            _logger.debug('Received data: %s' % data)
            # TODO: add concatenation of possible fragments.
            msg = self.serializer.deserialize(data)
            _logger.debug('Received message: %s' % msg)

            # TODO: add invocation context to support response association.
            map(lambda l: l.on_message_received(msg), self.listeners)

            # call internal handler of service level messages:
            self._on_message_received(msg)
            return True

        # else: received no data on a readable socket --> connection closed?
        _logger.warning('Frontend sent empty data.')
        return False

    def _close(self, sock):
        sock.close()
        self.sockets.remove(sock)

    def _on_message_received(self, msg):
        if isinstance(msg, Shutdown):
            _logger.debug('Frontend requested backend to shut down.')
            self.state = State.ShutdownPending