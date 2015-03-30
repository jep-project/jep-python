"""Framework independent PEP backend implementation."""
import logging
import socket
import select
import datetime
from jep.config import TIMEOUT_SELECT_SEC, BUFFER_LENGTH, TIMEOUT_LAST_MESSAGE
from jep.protocol import MessageSerializer
from jep.schema import Shutdown, BackendAlive

try:
    import enum
except ImportError:
    import jep.contrib.enum as enum

_logger = logging.getLogger(__name__)

#: Range to search for available ports.
PORT_RANGE = (9001, 9100)

#: Length of server's listen queue.
LISTEN_QUEUE_LENGTH = 3

#: Number of seconds between backend alive messages. Optimal: PERIOD_BACKEND_ALIVE_SEC = n * TIMEOUT_SELECT_SEC
TIMEOUT_BACKEND_ALIVE = datetime.timedelta(seconds=1)


class NoPortFoundError(Exception):
    pass


@enum.unique
class State(enum.Enum):
    Stopped = 1
    Running = 2
    ShutdownPending = 3


class Backend():
    """Synchronous JEP backend service."""

    def __init__(self, listeners=None):
        #: Message listeners.
        self.listeners = listeners or []
        #: Active sockets, [0] is the server socket.
        self.sockets = []
        #: Current state of backend.
        self.state = State.Stopped
        #: Timestamp of last alive message.
        self.ts_alive_sent = None
        #: Cache for BackendAlive message in serialized form.
        self.BACKEND_ALIVE_DATA = MessageSerializer().serialize(BackendAlive())
        #: Map of socket to frontend descriptor.
        self.frontend_by_socket = dict()

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
        assert not self.frontend_by_socket, 'Unexpected frontend connectors after shutdown.'

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
        print('JEP service, listening on port %d' % port, flush=True)

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
        self.frontend_by_socket[clientsocket] = FrontendConnector()
        _logger.info('Frontend connected.')

    def _receive(self, clientsocket):
        """Blocking read of client data on given socket."""
        data = None
        try:
            data = clientsocket.recv(BUFFER_LENGTH)
        except ConnectionAbortedError as e:
            _logger.warning('Data reception failed: %s' % e)

        if data:
            _logger.debug('Received data: %s' % data)
            frontend_connector = self.frontend_by_socket[clientsocket]
            frontend_connector.ts_last_data_received = datetime.datetime.now()
            frontend_connector.serializer.enque_data(data)

            for msg in frontend_connector.serializer:
                _logger.debug('Received message: %s' % msg)
                context = MessageContext(self, clientsocket)
                for listener in self.listeners:
                    # call listener's message specific handler method (visitor pattern's accept() call):
                    msg.invoke(listener, context)

                # call internal handler of service level messages:
                self._on_message_received(msg)
        else:
            _logger.info('Closing connection to frontend due to empty data reception.')
            self._close(clientsocket)

    def _close(self, sock):
        sock.close()
        self.sockets.remove(sock)
        self.frontend_by_socket.pop(sock, None)

    def _on_message_received(self, msg):
        """Handler for service level messages."""
        if isinstance(msg, Shutdown):
            _logger.debug('Frontend requested backend to shut down.')
            self.state = State.ShutdownPending

    def _cyclic(self):
        """Cyclic processing of service level tasks."""

        now = datetime.datetime.now()
        num_frontends = len(self.sockets) - 1
        if num_frontends > 0:

            # send alive message if front-end connected and message is due:
            if not self.ts_alive_sent or (now - self.ts_alive_sent >= TIMEOUT_BACKEND_ALIVE):
                _logger.debug('Sending alive message to %d frontend(s).' % num_frontends)

                for sock in self.sockets[1:]:
                    self._send_data(sock, self.BACKEND_ALIVE_DATA)
                self.ts_alive_sent = now

            # check timeouts for each connected frontend:
            for sock in self.sockets[1:].copy():
                if now - self.frontend_by_socket[sock].ts_last_data_received >= TIMEOUT_LAST_MESSAGE:
                    _logger.info('Disconnecting frontend after timeout.')
                    self._close(sock)

    def send_message(self, context, msg):
        """Message used by MessageContext only to delegate send."""
        _logger.debug('Sending message: %s.' % msg)
        serialized = self.frontend_by_socket[context.sock].serializer.serialize(msg)
        _logger.debug('Sending data: %s.' % serialized)
        self._send_data(context.sock, serialized)

    @classmethod
    def _send_data(cls, sock, data):
        sock.send(data)


class MessageContext:
    """Context of a request by frontend message."""

    # TODO: MessageContext + FrontendConnector --> FrontendConnection, to better align with frontend design.

    def __init__(self, service, sock):
        self.service = service
        self.sock = sock

    def send_message(self, msg):
        self.service.send_message(self, msg)


class FrontendConnector:
    """Information about a connected frontend."""

    def __init__(self, serializer=MessageSerializer()):
        #: Timestamp of last message received from this frontend (initialized due to accept).
        self.ts_last_data_received = datetime.datetime.now()

        #: Serializer used to decode data from frontend.
        self.serializer = serializer


class FrontendListener:
    """API to listen to messages from frontend, communicated via backend."""

    def on_shutdown(self, context):
        return NotImplemented

    def on_content_sync(self, content_sync, context):
        return NotImplemented

    def on_completion_request(self, completion_request, context):
        return NotImplemented

    def on_completion_invocation(self, completion_invocation, context):
        return NotImplemented