"""JEP frontend support."""
import collections
import logging
import re
import socket
import subprocess
import time
import select
import datetime

from jep.async import AsynchronousFileReader

from jep.config import ServiceConfigProvider, TIMEOUT_SELECT_SEC, BUFFER_LENGTH
from jep.protocol import MessageSerializer
from jep.schema import BackendAlive, Shutdown

try:
    import enum
except ImportError:
    import jep.contrib.enum as enum

_logger = logging.getLogger(__name__)

#: Regex to find service port announcement from backend.
PATTERN_PORT_ANNOUNCEMENT = re.compile(r'JEP service, listening on port (?P<port>\d+)')

#: Timeout to wait for backend shutdown.
TIMEOUT_BACKEND_SHUTDOWN = datetime.timedelta(seconds=5)

#: Timeout to wait for backend startup.
TIMEOUT_BACKEND_STARTUP = datetime.timedelta(seconds=5)


class Frontend:
    """Top level frontend class, once to be instantiated per editor plugin."""

    def __init__(self, listeners=None, service_config_provider=ServiceConfigProvider()):
        self.listeners = listeners or []
        self.service_config_provider = service_config_provider
        self.connection_by_service_selector = collections.defaultdict(lambda: None)

    def provide_connection(self, filename):
        """Returns connection to a backend service that can deal with the given file. Existing service connections are reused if possible."""
        _logger.debug('Service connector requested for file: %s' % filename)
        connection = None

        service_config = self.service_config_provider.provide_for(filename)
        if service_config:
            # check whether this service reference was used before:
            connection = self.connection_by_service_selector[service_config.selector]
            if connection:
                if not connection.service_config.checksum == self.service_config_provider.checksum(service_config.config_file_path):
                    # configuration changed:
                    _logger.debug('Config file %s changed, need to restart connection.')
                    connection.disconnect()
                    connection.connect()
                else:
                    _logger.debug('Using existing connection.')
            else:
                _logger.debug('Creating new connection.')
                connection = self._connect(service_config)
        else:
            _logger.warning('No service found for file %s.' % filename)

        return connection

    def _connect(self, service_config):
        """Connect to service described in configuration."""
        connection = BackendConnection(service_config, self.listeners)
        self.connection_by_service_selector[service_config.selector] = connection
        connection.connect()
        return connection


@enum.unique
class State(enum.Enum):
    """State of connection to backend service."""
    Disconnected = 1
    Connecting = 2
    Connected = 3
    DisconnectPending = 4


class BackendConnection:
    """Connection to a single backend service."""

    def __init__(self, service_config, listeners, serializer=MessageSerializer(), provide_async_reader=AsynchronousFileReader):
        self.service_config = service_config
        self.listeners = listeners
        self.state = State.Disconnected
        self._serializer = serializer
        self._provide_async_reader = provide_async_reader
        self._process = None
        self._process_output_reader = None
        self._socket = None
        self._ts_last_backend_timer_reset = None
        self._state_dispatch = {
            State.Connecting: self._run_connecting,
            State.Connected: self._run_connected,
            State.DisconnectPending: self._run_disconnect_pending
        }

    def connect(self):
        """Opens connection to backend service."""
        if self.state is not State.Disconnected:
            return

        self.state = State.Connecting

        # launch backend process and capture its output:
        _logger.debug('Starting backend service: %s' % self.service_config.command)
        self._process = subprocess.Popen(self.service_config.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self._process_output_reader = self._provide_async_reader(self._process.stdout)
        self._process_output_reader.start()
        self._ts_last_backend_timer_reset = datetime.datetime.now()

    def disconnect(self):
        """Closes connection to backend service."""
        self._disconnect(False)

    def run(self, timeout_sec=0.5):
        """Synchronous execution of connector statemachine."""
        self._state_dispatch[self.state](timeout_sec)
        time.sleep(0.2)

    def send_message(self, message):
        if self.state is State.Connected:
            _logger.debug('Sending message %s.' % message)
            data = self._serializer.serialize(message)
            _logger.debug('Sending data %s.' % data)
            self._socket.send(data)

    def _run_connecting(self, timeout_sec):
        # check for service's port announcement:
        lines = []
        self._read_service_output(0.2 * timeout_sec, lines)
        port = self._parse_port_announcement(lines)

        if not port:
            if datetime.datetime.now() - self._ts_last_backend_timer_reset > TIMEOUT_BACKEND_STARTUP:
                _logger.warning('Backend not starting up, aborting connection.')
                # TODO handle shutdown of process _and_ thread
                self._disconnect(True)
            return

        self._connect(port, 0.8 * timeout_sec)

    def _run_connected(self, timeout_sec):
        self._read_service_output(0.2 * timeout_sec)

        readable, *_ = select.select([self._socket], [], [], TIMEOUT_SELECT_SEC)
        _logger.debug('Readable sockets: %d' % len(readable))

        if readable:
            self._receive()

    def _run_disconnect_pending(self, timeout_sec):
        self._read_service_output(0.2 * timeout_sec)

        backend_process_running = self._process and self._process.poll() is None

        if self._process and not backend_process_running:
            _logger.debug('Backend process shut down gracefully.')
            self._process = None

        if backend_process_running and (datetime.datetime.now() - self._ts_last_backend_timer_reset > TIMEOUT_BACKEND_SHUTDOWN):
            _logger.warning('Backend still running and not observing shutdown protocol. Killing it.')
            self._kill_backend(backend_process_running)
            backend_process_running = False

        if not backend_process_running and self._process_output_reader:
            self._process_output_reader.join(timeout_sec)
            if self._process_output_reader.is_alive():
                _logger.warning('Output reader thread not stoppable. Possible memory leak.')
            else:
                _logger.debug('Output reader thread stopped.')
            self._read_service_output(0.2 * timeout_sec)
            self._process_output_reader = None
            self.state = State.Disconnected

    def _connect(self, port, timeout_sec):
        try:
            self._socket = socket.create_connection(('localhost', port), timeout_sec)
        except Exception as e:
            _logger.warning('Could not connect to backend at port %d within %.2f seconds.' % (port, timeout_sec))
            self._socket = None

        if self._socket:
            # initialize timer due to successful connection:
            self._ts_last_backend_timer_reset = datetime.datetime.now()
            self.state = State.Connected
        else:
            self._disconnect(True)

    def _receive(self):
        """Blocking read of backend data."""
        data = None
        try:
            data = self._socket.recv(BUFFER_LENGTH)
        except ConnectionResetError:
            _logger.warning('Backend closed connection unexpectedly.')

        if data:
            _logger.debug('Received data: %s' % data)
            self._serializer.enque_data(data)

            for msg in self._serializer.messages():
                _logger.debug('Received message: %s' % msg)
                for listener in self.listeners:
                    # call listener's message specific handler method (visitor pattern's accept() call):
                    msg.invoke(listener, self)

                # call internal handler of service level messages:
                self._on_message_received(msg)
        else:
            _logger.info('Closing connection to backend due to empty data reception.')
            self._disconnect(True)

    def _disconnect(self, connection_lost):
        if not connection_lost:
            self.send_message(Shutdown())

        if self._socket:
            self._socket.close()
            self._socket = None

        # start timer to wait for backend to shut down:
        self._ts_last_backend_timer_reset = datetime.datetime.now()

        if self.state is State.Connected:
            _logger.debug('Initiating disconnect.')
            self.state = State.DisconnectPending

    def _on_message_received(self, message):
        if isinstance(message, BackendAlive):
            self._ts_last_backend_timer_reset = datetime.datetime.now()
            _logger.debug('Backend is still alive.')


    @classmethod
    def _parse_port_announcement(cls, lines):
        port = None
        for line in lines:
            m = PATTERN_PORT_ANNOUNCEMENT.search(line)
            if m:
                port = int(m.group('port'))
                _logger.debug('Backend announced listening at port %d.' % port)
                break
        return port

    def _read_service_output(self, timeout_sec=0.0, result_lines=None):
        while not self._process_output_reader.queue_.empty():
            line = self._process_output_reader.queue_.get().strip()
            _logger.debug('[backend] >>>%s<<<' % line)
            if result_lines is not None:
                result_lines.append(line)

    def _kill_backend(self, backend_process_running):
        self._process.kill()
        self._process = None


class BackendListener:
    """API to listen to messages from backend, communicated by frontend."""

    def on_backend_alive(self, context):
        return NotImplemented

    def on_out_of_sync(self, out_of_sync, context):
        return NotImplemented

    def on_content_sync(self, content_sync, context):
        return NotImplemented

    def on_problem_update(self, problem_update, context):
        return NotImplemented

    def on_completion_response(self, completion_response, context):
        return NotImplemented