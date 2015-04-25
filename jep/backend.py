"""Framework independent PEP backend implementation."""
import datetime
import enum
import logging
import socket
import select
from jep.config import TIMEOUT_SELECT_SEC, BUFFER_LENGTH, TIMEOUT_LAST_MESSAGE
from jep.protocol import MessageSerializer
from jep.schema import Shutdown, BackendAlive, ContentSync, OutOfSync

_logger = logging.getLogger(__name__)

#: Range to search for available ports.
PORT_RANGE = (9001, 9100)

#: Length of server's listen queue.
LISTEN_QUEUE_LENGTH = 3

#: Number of seconds between backend alive messages. Optimal: PERIOD_BACKEND_ALIVE_SEC = n * TIMEOUT_SELECT_SEC
TIMEOUT_BACKEND_ALIVE = datetime.timedelta(minutes=1)


class NoPortFoundError(Exception):
    pass


@enum.unique
class State(enum.Enum):
    Stopped = 1
    Running = 2
    ShutdownPending = 3


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


class Backend(FrontendListener):
    """Synchronous JEP backend service."""

    def __init__(self, listeners=None):
        #: User message listeners.
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
        self.connection = dict()

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
        assert not self.connection, 'Unexpected frontend connectors after shutdown.'

    def stop(self):
        _logger.debug('Received request to shut down.')
        self.state = State.ShutdownPending

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
        clientsocket.setblocking(0)
        self.sockets.append(clientsocket)
        self.connection[clientsocket] = FrontendConnection(self, clientsocket)
        _logger.info('Frontend %d connected.' % id(clientsocket))

    def _receive(self, clientsocket):
        """Read of client data on given socket."""

        frontend_connector = self.connection[clientsocket]
        cycles = 0
        try:
            while True:
                data = clientsocket.recv(BUFFER_LENGTH)
                cycles += 1

                if data:
                    _logger.debug('Received data: %s' % data)
                    frontend_connector.ts_last_data_received = datetime.datetime.now()
                    frontend_connector.serializer.enque_data(data)
                else:
                    _logger.debug('Socket closed by frontend.')
                    raise ConnectionAbortedError()
        except ConnectionAbortedError:
            _logger.debug('Closing connection to frontend due to closed socket.')
            self._close(clientsocket)
        except BlockingIOError as e:
            # leave receive loop for now as no more data is available:
            pass

        _logger.debug('Read data in %d cycles.' % cycles)

        for msg in frontend_connector.serializer:
            _logger.debug('Received message: %s' % msg)
            for listener in self.listeners:
                # call listener's message specific handler method (visitor pattern's accept() call):
                msg.invoke(listener, frontend_connector)

            # call backend directly for internally handled messages:
            msg.invoke(self, frontend_connector)

    def _close(self, sock):
        _logger.info('Socket %d disconnected.' % id(sock))
        sock.close()
        self.sockets.remove(sock)
        self.connection.pop(sock, None)

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
                if now - self.connection[sock].ts_last_data_received >= TIMEOUT_LAST_MESSAGE:
                    _logger.debug('Disconnecting frontend after timeout.')
                    self._close(sock)

    def send_message(self, connection, msg):
        """Message used by MessageContext only to delegate send."""
        _logger.debug('Sending message: %s.' % msg)
        serialized = self.connection[connection.sock].serializer.serialize(msg)
        _logger.debug('Sending data: %s.' % serialized)
        self._send_data(connection.sock, serialized)

    @classmethod
    def _send_data(cls, sock, data):
        sock.send(data)

    def on_shutdown(self, context):
        self.stop()

    def on_content_sync(self, content_sync: ContentSync, context):
        content = self.content_by_filepath[content_sync.file]
        length = len(content)

        if content_sync.start > length:
            _logger.warning('Received content sync for %s starting at index %d but known content length is only %d.' % (content_sync.file, content_sync.start, length))
            context.send_message(OutOfSync(content_sync.file))
            return

        start = content_sync.start
        end = content_sync.end if content_sync.end is not None else length

        if start < 0:
            start = 0
        if end < 0:
            end = 0

        _logger.debug('Updating file %s from index %d to %d: %s' % (content_sync.file, start, end, content_sync.data))
        content[start:end] = content_sync.data


class FrontendConnection:
    """Connection to frontend instance."""

    def __init__(self, service, sock, serializer=None):
        # Backend instance that created this connection.
        self.service = service
        # Socket used to talk to frontend.
        self.sock = sock
        #: Timestamp of last message received from this frontend (initialized due to accept).
        self.ts_last_data_received = datetime.datetime.now()

        #: Serializer used to decode data from frontend.
        self.serializer = serializer or MessageSerializer()

    def send_message(self, msg):
        self.service.send_message(self, msg)
