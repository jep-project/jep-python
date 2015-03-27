"""JEP frontend support."""
import collections
import logging
import re
import socket
import subprocess
import time

from jep.async import AsynchronousFileReader
from jep.config import ServiceConfigProvider
from jep.protocol import MessageSerializer

try:
    import enum
except ImportError:
    import jep.contrib.enum as enum


_logger = logging.getLogger(__name__)

#: Regex to find service port announcement from backend.
PATTERN_PORT_ANNOUNCEMENT = re.compile(r'JEP service, listening on port (?P<port>\d+)')

#: Number of seconds between select timeouts.
TIMEOUT_SELECT_SEC = 0.1


class Frontend:
    """Top level frontend class, once to be instantiated per editor plugin."""

    def __init__(self, listeners=None, service_config_provider=ServiceConfigProvider()):
        self.listeners = listeners
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
                    connection.close()
                    connection.open()
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
        connection.open()
        return connection

    def _disconnect(self, service_config):
        """Disconnect from service described in configuration."""
        connection = self.connection_by_service_selector.pop(service_config.selector)
        connection.close()


@enum.unique
class State(enum.Enum):
    """State of connection to backend service."""
    Disconnected = 1
    Connecting = 2
    Connected = 3


class BackendConnection:
    """Connection to a single backend service."""

    def __init__(self, service_config, listeners, serializer=MessageSerializer()):
        self.service_config = service_config
        self.listeners = listeners
        self.serializer = serializer
        self.state = State.Disconnected
        self.process = None
        self.process_output_reader = None
        self.sock = None

        # state dispatcher:
        self._state_dispatch = collections.defaultdict(lambda: self._run_unhandled)
        self._state_dispatch[State.Connecting] = self._run_connecting
        self._state_dispatch[State.Connected] = self._run_connected

    def open(self):
        """Opens connection to backend service."""
        if self.state is not State.Disconnected:
            return

        self.state = State.Connecting

        # launch backend process and capture its output:
        _logger.debug('Starting backend service: %s' % self.service_config.command)
        self.process = subprocess.Popen(self.service_config.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self.process_output_reader = AsynchronousFileReader(self.process.stdout)
        self.process_output_reader.start()

    def close(self):
        """Closes connection to backend service."""
        pass

    def run(self, timeout_sec=0.5):
        """Synchronous execution of connector statemachine."""
        self._state_dispatch[self.state](timeout_sec)
        time.sleep(0.2)

    def send_message(self, message):
        if self.state is State.Connected:
            _logger.debug('Sending message %s.' % message)
            data = self.serializer.serialize(message)
            _logger.debug('Sending data %s.' % data)
            self.sock.send(data)

    def _run_unhandled(self, timeout_sec):
        self._read_service_output(timeout_sec)

    def _run_connecting(self, timeout_sec):
        # check for service's port announcement:
        lines = []
        self._read_service_output(0.2 * timeout_sec, lines)
        port = self._parse_port_announcement(lines)

        if not port:
            # TODO implement timeout.
            return

        self._connect(port, 0.8 * timeout_sec)

    def _run_connected(self, timeout_sec):
        self._read_service_output(0.2 * timeout_sec)
        # TODO receive logic via select
        # TODO cyclic tasks, e.g. alive supervision of backend
        # TODO process supervision
        pass

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

    def _connect(self, port, timeout_sec):
        try:
            self.sock = socket.create_connection(('localhost', port), timeout_sec)
        except Exception as e:
            _logger.warning('Could not connect to backend at port %d within %.2f seconds.' % (port, timeout_sec))
            self.sock = None

        if self.sock:
            self.state = State.Connected
        else:
            self._disconnect()

    def _disconnect(self):
        # TODO try graceful shutdown.
        # TODO timeout.
        if self.sock:
            _logger.debug('Closing socket to backend.')
            self.sock.close()
            self.sock = None

        if self.process:
            _logger.debug('Killing backend process.')
            self.process.kill()
            self.process = None

    def _read_service_output(self, timeout_sec=0.0, result_lines=None):
        while not self.process_output_reader.queue_.empty():
            line = self.process_output_reader.queue_.get().strip()
            _logger.debug('[backend] >>>%s<<<' % line)
            if result_lines is not None:
                result_lines.append(line)


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