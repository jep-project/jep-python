"""Framework independent PEP backend implementation."""
import enum
import logging
import socket
import select
import datetime
from jep.protocol import MessageSerializer
from jep.schema import Shutdown, BackendAlive

_logger = logging.getLogger(__name__)

#: Range to search for available ports.
PORT_RANGE = (9001, 9100)

#: Length of server's listen queue.
LISTEN_QUEUE_LENGTH = 3

#: Data buffer length in bytes.
BUFFER_LENGTH = 10000

#: Number of seconds between select timeouts.
TIMEOUT_SELECT_SEC = 0.5

#: Number of seconds between backend alive messages. Optimal: PERIOD_BACKEND_ALIVE_SEC = n * TIMEOUT_SELECT_SEC
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
        #: Serializer used for message serialization and deserialization.
        self.serializer = serializer or MessageSerializer()
        #: Message listeners.
        self.listeners = listeners or []
        #: Active sockets, [0] is the server socket.
        self.sockets = []
        #: Current state of backend.
        self.state = State.Stopped
        #: Timestamp of last alive message.
        self.alive_sent = None
        #: Cache for BackendAlive message in serialized form.
        self.backend_alive_data = self.serializer.serialize(BackendAlive())

    @property
    def serversocket(self):
        return self.sockets[0] if self.sockets else None

    def start(self):
        """Starts listening for front-ends to connect."""

        assert self.state is State.Stopped

        _logger.info('Starting backend.')
        self._listen()
        self._run()
        _logger.info('Backend stopped.')

        assert self.state is State.Stopped
        assert not self.sockets, 'Unexpected active sockets after shutdown.'

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
                    self._receive(sock)

            self._cyclic()

        if self.state == State.ShutdownPending:
            for sock in self.sockets.copy():
                self._close(sock)
            self.state = State.Stopped

    def _accept(self):
        """Blocking accept of incoming connection."""
        clientsocket, *_ = self.serversocket.accept()
        self.sockets.append(clientsocket)
        _logger.info('Frontend connected.')

    def _receive(self, clientsocket):
        """Blocking read of client data on given socket."""
        data = clientsocket.recv(BUFFER_LENGTH)
        if data:
            _logger.debug('Received data: %s' % data)
            # TODO: add concatenation of possible fragments.
            msg = self.serializer.deserialize(data)
            _logger.debug('Received message: %s' % msg)

            context = MessageContext(self, clientsocket)
            for listener in self.listeners:
                listener.on_message_received(msg, context)

            # call internal handler of service level messages:
            self._on_message_received(msg)
            return True

        else:
            _logger.info('Closing connection to frontend due to empty data reception.')
            self._close(clientsocket)
            return False

    def _close(self, sock):
        sock.close()
        self.sockets.remove(sock)

    def _on_message_received(self, msg):
        """Handler for service level messages."""
        if isinstance(msg, Shutdown):
            _logger.debug('Frontend requested backend to shut down.')
            self.state = State.ShutdownPending

    def _cyclic(self):
        """Cyclic processing of service level tasks."""

        # send alive message if front-end connected and message is due:
        num_frontends = len(self.sockets) - 1
        if num_frontends > 0:
            now = datetime.datetime.now()
            if not self.alive_sent or (now - self.alive_sent) >= datetime.timedelta(seconds=PERIOD_BACKEND_ALIVE_SEC):
                _logger.debug('Sending alive message to %d frontend(s).' % num_frontends)

                for sock in self.sockets[1:]:
                    self._send_data(sock, self.backend_alive_data)
                self.alive_sent = now

    def send_message(self, context, msg):
        """Message used by MessageContext only to delegate send."""
        _logger.debug('Sending message: %s.' % msg)
        serialized = self.serializer.serialize(msg)
        _logger.debug('Sending data: %s.' % serialized)
        self._send_data(context.sock, serialized)

    @classmethod
    def _send_data(cls, sock, data):
        sock.send(data)


class MessageContext:
    """Context of a request by frontend message."""

    def __init__(self, service, sock):
        self.service = service
        self.sock = sock

    def send_message(self, msg):
        self.service.send_message(self, msg)