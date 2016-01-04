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
import uuid
from jep_py.async import AsynchronousFileReader
from jep_py.config import ServiceConfigProvider, BUFFER_LENGTH, TIMEOUT_LAST_MESSAGE
from jep_py.protocol import MessageSerializer
from jep_py.schema import Shutdown, TOKEN_ATTR_NAME
from jep_py.syntax import SyntaxFileSet

_logger = logging.getLogger(__name__)

#: Regex to find backend port announcement from backend.
PATTERN_PORT_ANNOUNCEMENT = re.compile(r'JEP service, listening on port (?P<port>\d+)')

#: Timeout to wait for backend startup.
TIMEOUT_BACKEND_STARTUP = datetime.timedelta(seconds=5)

#: Timeout to wait for backend shutdown.
TIMEOUT_BACKEND_SHUTDOWN = datetime.timedelta(seconds=5)


class BackendListener:
    """API to listen to messages from backend, communicated by frontend."""

    def on_connection_state_changed(self, old_state, new_state, context):
        return NotImplemented

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

    def on_static_syntax_list(self, format_, syntaxes, context):
        return NotImplemented


class Frontend(BackendListener):
    """Top level frontend class, once to be instantiated per editor plugin."""

    def __init__(self, listeners=None, *, service_config_provider=None, provide_backend_connection=None):
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
                    if connection.state is State.Disconnected:
                        # reattempt to connect:
                        _logger.debug('   ...and reconnecting it.')
                        connection.connect()
            else:
                _logger.debug('Creating new connection.')
                connection = self._connect(service_config)
        else:
            _logger.warning('No service found for file %s.' % filename)

        return connection

    def _connect(self, service_config):
        """Connect to service described in configuration."""
        connection = self.provide_backend_connection(self, service_config, self.listeners)
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


class BackendConnection():
    """Connection to a single backend service."""

    def __init__(self, frontend, service_config, listeners, *, serializer=None, provide_async_reader=None):
        self.frontend = frontend
        self.service_config = service_config
        self.listeners = listeners
        self._state = State.Disconnected
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
        #: Token used for pending request.
        self._current_request_token = None
        #: Message received as response to pending request.
        self._current_request_response = None

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, next_state):
        old_state = self._state
        self._state = next_state
        if next_state is not old_state:
            for listener in self.listeners:
                listener.on_connection_state_changed(old_state, next_state, self)

    def connect(self):
        """Opens connection to backend service."""
        if self.state is not State.Disconnected:
            _logger.warning('Cannot connect while in state %s.' % self.state.name)
            return

        # launch backend process and capture its output:
        cwd = os.path.dirname(self.service_config.config_file_path)
        _logger.debug('Starting backend service with command "%s" in directory %s.' % (self.service_config.command, cwd))
        try:
            # on Windows prevent console window when being called from GUI process:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # default: startupinfo.wShowWindow = subprocess.SW_HIDE
        except AttributeError:
            # non-Windows system:
            startupinfo = None

        try:
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
        except Exception as e:
            _logger.warning('Failed to start backend service with command "%s" in directory %s with exception %s.' % (self.service_config.command, cwd, e))
            # prevent recursion:
            self._reconnect_expected = False
            self._cleanup()

    def disconnect(self):
        """Closes connection to backend service."""
        self._reconnect_expected = False
        self.send_message(Shutdown())
        self._state_timer_reset = datetime.datetime.now()
        self.state = State.Disconnecting

    def reconnect(self, service_config=None):
        """Reconnects to new service configuration."""
        _logger.debug('Reconnecting.')
        self.disconnect()
        if service_config:
            self.service_config = service_config
        self._reconnect_expected = True

    def run(self, duration):
        """Synchronous execution of connector statemachine."""
        now = datetime.datetime.now()
        endtime = now + duration

        response_expected = self._current_request_token is not None and self._current_request_response is None
        response_received = False

        while now < endtime and (not response_expected or not response_received):
            self._dispatch(endtime - now)
            now = datetime.datetime.now()
            response_received = self._current_request_response is not None

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

    def request_message(self, message, duration):
        """Sends a request message and waits synchronously for the response from backend.

        While waiting, other asynchronous messages may be received and processed, but only one synchronous request may be active at a given time (for now). The functions
        returns immediately upon reception of the response or after waiting for the given timeout period.

        Synchronous invocation is only possible for message types that have a dedicated response message type and therefore carry a request ``token`` attribute. The
        method should be used only in situations where the frontend host (e.g. the IDE) demands synchronous processing, e.g. to get immediate feedback for possible
        code completion options.

        If the request class' token attribute is still ``None`` it is filled with a unique ID by this method. If it holds a value that value is used and the caller is
        responsible for uniqueness (in most general case at backend level).

        :param message: The request message to be sent to backend. The underlying message class must have a ``token`` attribute.
        :param duration: Maximal period to wait for response.
        :return: Response message object or ``None``.
        """

        # currently only one active request is possible:
        if self._current_request_token is not None:
            _logger.warning('Already service a request with token %s, so new request is skipped.' % self._current_request_token)

        if self.state is State.Connected:
            # make sure message object has token attribute and fill it if necessary:
            token = getattr(message, TOKEN_ATTR_NAME)
            if token is None:
                token = uuid.uuid1().hex
                _logger.debug('Assigning request token %s.' % token)
                setattr(message, TOKEN_ATTR_NAME, token)

            self._current_request_token = token
            self.send_message(message)
            _logger.debug('Waiting for response message.')
            self.run(duration)
            self._current_request_token = None
            response = self._current_request_response
            self._current_request_response = None

            return response
        else:
            _logger.warning('Skipping request message, since connector is not connected.')
            return None

    def _run_disconnected(self, duration):
        #_logger.debug('Not doing anything while disconnected, but reconnect expected is %s' % self._reconnect_expected)
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
            _logger.debug('Backend did not sent any message for %.2f seconds, reconnecting.' % TIMEOUT_LAST_MESSAGE.total_seconds())
            self.reconnect()

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
                _logger.info('Connected to backend command %s' % self.service_config.command)
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
                    _logger.debug('Socket closed by backend.')
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

            # first allow processing of global messages by frontend:
            msg.invoke(self.frontend, self)

            # call listeners' message specific handler methods (visitor pattern's accept() call):
            for listener in self.listeners:
                msg.invoke(listener, self)

            # handle response messages:
            if self._current_request_token is not None:
                self.check_response_message(msg)

    def check_response_message(self, msg):
        token = getattr(msg, 'token', None)
        if token == self._current_request_token:
            _logger.debug('Received response message for token %s.' % token)
            self._current_request_token = None
            self._current_request_response = msg

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
        _logger.info('Disconnected from backend.')

        if self._reconnect_expected:
            _logger.debug('Attempting to reconnect.')
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
        if self._process_output_reader:
            while not self._process_output_reader.queue_.empty():
                line = self._process_output_reader.queue_.get().strip()
                _logger.debug('[backend] %s' % line)
                if result_lines is not None:
                    result_lines.append(line)
