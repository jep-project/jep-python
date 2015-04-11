"""JEP frontend support."""
import enum
import collections
import logging
import platform
import re
import socket
import subprocess
import select
import shlex
import datetime
import os
from os import path

from jep.async import AsynchronousFileReader
from jep.config import ServiceConfigProvider, BUFFER_LENGTH, TIMEOUT_LAST_MESSAGE
from jep.protocol import MessageSerializer
from jep.schema import Shutdown

_logger = logging.getLogger(__name__)

#: Regex to find backend port announcement from backend.
PATTERN_PORT_ANNOUNCEMENT = re.compile(r'JEP service, listening on port (?P<port>\d+)')

#: Timeout to wait for backend startup.
TIMEOUT_BACKEND_STARTUP = datetime.timedelta(seconds=5)

#: Timeout to wait for backend shutdown.
TIMEOUT_BACKEND_SHUTDOWN = datetime.timedelta(seconds=5)


class Frontend:
    """Top level frontend class, once to be instantiated per editor plugin."""

    def __init__(self, listeners=None, service_config_provider=None, provide_backend_connection=None):
        self.listeners = listeners or []
        self.service_config_provider = service_config_provider or ServiceConfigProvider()
        self.provide_backend_connection = provide_backend_connection or BackendConnection
        self.connection_by_service_selector = collections.defaultdict(lambda: None)

    def get_connection(self, filename):
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
                    _logger.debug('Config file %s changed, need to renew connection.' % service_config.config_file_path)

                    # disconnect old and return new one (as disconnect can take a few cycles):
                    connection.reconnect(service_config)
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
        connection = self.provide_backend_connection(service_config, self.listeners)
        self.connection_by_service_selector[service_config.selector] = connection
        connection.connect()
        return connection


@enum.unique
class State(enum.Enum):
    """State of connection to backend service."""
    Disconnected = 1
    Connecting = 2
    Connected = 3
    Disconnecting = 4


class BackendConnection:
    """Connection to a single backend service."""

    def __init__(self, service_config, listeners, serializer=None, provide_async_reader=None):
        self.service_config = service_config
        self.listeners = listeners
        self.state = State.Disconnected
        self._serializer = serializer or MessageSerializer()
        self._provide_async_reader = provide_async_reader or AsynchronousFileReader
        self._process = None
        self._process_output_reader = None
        self._socket = None
        self._state_timer_reset = None
        self._state_handler = {
            State.Connecting: self._run_connecting,
            State.Connected: self._run_connected,
            State.Disconnecting: self._run_disconnecting,
            State.Disconnected: self._run_disconnected
        }
        #: Does the user expect the connection to be reestablished e.g. after the backend died?
        self._reconnect_expected = False

    def connect(self):
        """Opens connection to backend service."""
        if self.state is not State.Disconnected:
            _logger.warning('Cannot connect while in state %s.' % self.state.name)
            return

        # launch backend process and capture its output:
        cwd = path.dirname(self.service_config.config_file_path)
        _logger.debug('Starting backend service with command "%s" in directory %s.' % (self.service_config.command, cwd))
        try:
            # on Windows prevent console window when being called from GUI process:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # default: startupinfo.wShowWindow = subprocess.SW_HIDE
        except AttributeError:
            # non-Windows system:
            startupinfo = None

        # make cwd the command search start folder as well as the current dir of the command itself:
        os.chdir(cwd)
        self._process = subprocess.Popen(shlex.split(self.service_config.command, posix=not platform.system() == 'Windows'),
                                         cwd=cwd,
                                         startupinfo=startupinfo,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT,
                                         universal_newlines=True)
        self._process_output_reader = self._provide_async_reader(self._process.stdout)
        self._process_output_reader.start()

        self._state_timer_reset = datetime.datetime.now()
        self.state = State.Connecting

    def disconnect(self):
        """Closes connection to backend service."""
        self._reconnect_expected = False
        self.send_message(Shutdown())
        self._state_timer_reset = datetime.datetime.now()
        self.state = State.Disconnecting

    def reconnect(self, service_config):
        """Reconnects to new service configuration."""
        _logger.info('Reconnecting due to changed service configuration.')
        self.disconnect()
        self.service_config = service_config
        self._reconnect_expected = True

    def run(self, duration):
        """Synchronous execution of connector statemachine."""
        now = datetime.datetime.now()
        endtime = now + duration

        while now < endtime:
            self._dispatch(endtime - now)
            now = datetime.datetime.now()

    def _dispatch(self, duration):
        """State dispatch, extracted out for testability."""
        self._state_handler[self.state](duration)

    def send_message(self, message):
        if self.state is State.Connected:
            try:
                _logger.debug('Sending message %s.' % message)
                data = self._serializer.serialize(message)
                _logger.debug('Sending data %s.' % data)
                self._socket.send(data)
            except Exception as e:
                _logger.warning('Sending message failed: %s' % e)
        else:
            _logger.warning('In state %s no messages are sent to backend, but received request to send %s.' % (self.state, message))

    def _run_disconnected(self, duration):
        pass

    def _run_connecting(self, duration):
        # check for backend's port announcement:
        lines = []
        self._read_backend_output(lines)
        port = self._parse_port_announcement(lines)

        if not port:
            if datetime.datetime.now() - self._state_timer_reset > TIMEOUT_BACKEND_STARTUP:
                _logger.warning('Backend not starting up, aborting connection.')
                self._cleanup(duration)
            return

        self._connect(port, duration)

    def _run_connected(self, duration):
        self._read_backend_output()

        readable, *_ = select.select([self._socket], [], [], duration.total_seconds())
        if readable:
            self._receive()

        if datetime.datetime.now() - self._state_timer_reset > TIMEOUT_LAST_MESSAGE:
            _logger.debug('Backend did not sent any message for %.2f seconds, disconnecting.' % TIMEOUT_LAST_MESSAGE.total_seconds())
            self.disconnect()

    def _run_disconnecting(self, duration):
        self._read_backend_output()
        if self._process:
            backend_process_running = self._process.poll() is None
            if backend_process_running:
                if datetime.datetime.now() - self._state_timer_reset > TIMEOUT_BACKEND_SHUTDOWN:
                    _logger.warning('Backend still running and not observing shutdown protocol.')
                    self._cleanup(duration)
            else:
                _logger.debug('Backend process shut down gracefully.')
                self._process = None
                self._cleanup(duration)
        else:
            self._cleanup(duration)

    def _connect(self, port, duration):
        try:
            self._socket = socket.create_connection(('localhost', port), duration.total_seconds())
            if self._socket:
                self._socket.setblocking(0)
                self._state_timer_reset = datetime.datetime.now()
                self.state = State.Connected

                # from now on, only the user can stop this connection for good:
                self._reconnect_expected = True
            else:
                _logger.warning('Could not connect to backend at port %d within %.2f seconds (socket is None).' % (port, duration.total_seconds()))
                self._cleanup(duration)
        except Exception as e:
            _logger.warning('Could not connect to backend at port %d within %.2f seconds.' % (port, duration.total_seconds()))
            self._socket = None
            self._cleanup(duration)

    def _receive(self):
        """Read of backend data."""
        cycles = 0
        try:
            while True:
                data = self._socket.recv(BUFFER_LENGTH)
                cycles += 1

                if data:
                    # any received message resets the timeout:
                    self._state_timer_reset = datetime.datetime.now()

                    _logger.debug('Received data: %s' % data)
                    self._serializer.enque_data(data)
                else:
                    _logger.info('Socket closed by backend.')
                    raise ConnectionResetError()
        except ConnectionResetError:
            _logger.warning('Backend closed connection unexpectedly.')
            self._cleanup()
        except BlockingIOError as e:
            # leave receive loop for now as no more data is available:
            pass

        _logger.debug('Read data in %d cycles.' % cycles)

        for msg in self._serializer:
            _logger.debug('Received message: %s' % msg)
            for listener in self.listeners:
                # call listener's message specific handler method (visitor pattern's accept() call):
                msg.invoke(listener, self)

    def _cleanup(self, duration=datetime.timedelta(seconds=0.01)):
        """Internal hard disconnect. Ensures all resources (sockets, processes, threads) are released."""

        # close socket if needed:
        if self._socket:
            self._socket.close()
            self._socket = None

        # kill process if still running (graceful shutdown tried elsewhere):
        if self._process:
            _logger.warning('Killing backend process.')
            self._process.kill()
            self._process = None

        # stop thread reading process output:
        if self._process_output_reader:
            self._process_output_reader.join(duration.total_seconds())
            if self._process_output_reader.is_alive():
                _logger.warning('Output reader thread not stoppable. Possible memory leak.')
            else:
                _logger.debug('Output reader thread stopped.')
            self._read_backend_output()
            self._process_output_reader = None

        self.state = State.Disconnected

        if self._reconnect_expected:
            _logger.debug('Reconnecting since this disconnect was not initiated by user.')
            self.connect()

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

    def _read_backend_output(self, result_lines=None):
        while not self._process_output_reader.queue_.empty():
            line = self._process_output_reader.queue_.get().strip()
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