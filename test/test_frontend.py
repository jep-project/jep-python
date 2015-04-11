import os
from os import path
import queue
from unittest import mock
import datetime
import itertools
from jep.config import TIMEOUT_LAST_MESSAGE
from jep.frontend import Frontend, State, BackendConnection, TIMEOUT_BACKEND_STARTUP, TIMEOUT_BACKEND_SHUTDOWN
from jep.schema import Shutdown, BackendAlive
from test.logconfig import configure_test_logger


def setup_function(function):
    configure_test_logger()
    # make sure all test function start from input folder:
    os.chdir(os.path.join(os.path.dirname(__file__), 'input'))


def test_provide_connection_unhandled_file():
    frontend = Frontend()
    assert not frontend.get_connection('some.unknown')


def test_provide_connection_first_time():
    mock_service_config = mock.MagicMock()
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR
    mock_service_config_provider = mock.MagicMock()
    mock_service_config_provider.provide_for = mock.MagicMock(return_value=mock_service_config)

    mock_connection = mock.MagicMock()
    mock_provide_backend_connection = mock.MagicMock(return_value=mock_connection)

    frontend = Frontend(mock.sentinel.LISTENERS, mock_service_config_provider, mock_provide_backend_connection)
    connection = frontend.get_connection(mock.sentinel.FILE_NAME)

    mock_service_config_provider.provide_for.assert_called_once_with(mock.sentinel.FILE_NAME)
    mock_provide_backend_connection.assert_called_once_with(mock_service_config, mock.sentinel.LISTENERS)
    mock_connection.connect.assert_called_once()
    assert not mock_connection.disconnect.called
    assert connection is mock_connection


def test_provide_connection_second_time_with_matching_selector_and_matching_checksum():
    mock_service_config = mock.MagicMock()
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR
    mock_service_config_provider = mock.MagicMock()
    mock_service_config_provider.provide_for = mock.MagicMock(return_value=mock_service_config)
    mock_service_config_provider.checksum = mock.MagicMock(return_value=mock.sentinel.CONFIG_CHECKSUM)

    mock_connection = mock.MagicMock()
    mock_connection.service_config.checksum = mock.sentinel.CONFIG_CHECKSUM
    mock_provide_backend_connection = mock.MagicMock(return_value=mock_connection)

    frontend = Frontend(mock.sentinel.LISTENERS, mock_service_config_provider, mock_provide_backend_connection)
    connection1 = frontend.get_connection(mock.sentinel.FILE_NAME1)
    assert mock_connection.connect.called
    mock_connection.connect.reset_mock()

    connection2 = frontend.get_connection(mock.sentinel.FILE_NAME2)
    assert connection1 is connection2
    assert not mock_connection.connect.called
    assert not mock_connection.disconnect.called
    assert [mock.call.provide_for(mock.sentinel.FILE_NAME1), mock.call.provide_for(mock.sentinel.FILE_NAME2)] in mock_service_config_provider.method_calls
    assert mock_provide_backend_connection.call_count == 1


def test_provide_connection_second_time_with_matching_selector_and_new_checksum():
    mock_service_config = mock.MagicMock()
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR
    mock_service_config_provider = mock.MagicMock()
    mock_service_config_provider.provide_for = mock.MagicMock(return_value=mock_service_config)
    mock_service_config_provider.checksum = mock.MagicMock(return_value=mock.sentinel.CONFIG_CHECKSUM)

    mock_connection = mock.MagicMock()
    mock_connection.service_config.checksum = mock.sentinel.CONFIG_CHECKSUM
    mock_provide_backend_connection = mock.MagicMock(return_value=mock_connection)

    frontend = Frontend(mock.sentinel.LISTENERS, mock_service_config_provider, mock_provide_backend_connection)
    connection1 = frontend.get_connection(mock.sentinel.FILE_NAME1)
    assert mock_connection.connect.called
    mock_connection.reset_mock()

    # now change the checksum of the provided service configuration:
    mock_service_config_provider.checksum = mock.MagicMock(return_value=mock.sentinel.CONFIG_CHECKSUM2)
    mock_connection2 = mock.MagicMock()
    mock_connection2.service_config.checksum = mock.sentinel.CONFIG_CHECKSUM
    mock_provide_backend_connection.return_value = mock_connection2

    connection2 = frontend.get_connection(mock.sentinel.FILE_NAME2)

    # new connection:
    assert connection1 is not connection2
    assert connection2 is mock_connection2
    assert mock_connection.method_calls == [mock.call.disconnect()]
    assert mock_connection2.method_calls == [mock.call.connect()]
    assert mock_provide_backend_connection.call_count == 2


def test_provide_connection_second_time_with_other_selector():
    mock_service_config = mock.MagicMock()
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR
    mock_service_config_provider = mock.MagicMock()
    mock_service_config_provider.provide_for = mock.MagicMock(return_value=mock_service_config)

    mock_connection = mock.MagicMock()
    mock_provide_backend_connection = mock.MagicMock(return_value=mock_connection)

    frontend = Frontend(mock.sentinel.LISTENERS, mock_service_config_provider, mock_provide_backend_connection)
    frontend.get_connection(mock.sentinel.FILE_NAME1)
    assert mock_connection.connect.called
    mock_connection.connect.reset_mock()

    # now change the selector of the provided service configuration:
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR2

    frontend.get_connection(mock.sentinel.FILE_NAME2)
    assert mock_provide_backend_connection.call_count == 2


def test_backend_connection_initial_state():
    connection = BackendConnection(mock.sentinel.SERVICE_CONFIG, mock.sentinel.LISTENERS)
    assert connection.state is State.Disconnected


def test_backend_connection_send_message_ok():
    mock_serializer = mock.MagicMock()
    mock_serializer.serialize = mock.MagicMock(return_value=mock.sentinel.SERIALIZED)
    mock_socket = mock.MagicMock()
    mock_socket.send = mock.MagicMock()

    connection = BackendConnection(mock.sentinel.SERVICE_CONFIG, mock.sentinel.LISTENERS, serializer=mock_serializer)
    connection._socket = mock_socket
    connection.state = State.Connected

    # we have a socket and are connected, so sending the message must go through just fine:
    connection.send_message(mock.sentinel.MESSAGE)

    mock_serializer.serialize.assert_called_once_with(mock.sentinel.MESSAGE)
    mock_socket.send.assert_called_once_with(mock.sentinel.SERIALIZED)


def test_backend_connection_send_message_wrong_state():
    mock_serializer = mock.MagicMock()
    mock_serializer.serialize = mock.MagicMock(return_value=mock.sentinel.SERIALIZED)
    mock_socket = mock.MagicMock()
    mock_socket.send = mock.MagicMock()

    connection = BackendConnection(mock.sentinel.SERVICE_CONFIG, mock.sentinel.LISTENERS, serializer=mock_serializer)
    connection._socket = mock_socket

    # no message is sent in any state that is not connected:
    for state in {State.Disconnected, State.Connecting, State.Disconnecting}:
        connection.state = state
        connection.send_message(mock.sentinel.MESSAGE)
        assert not mock_serializer.serialize.called
        assert not mock_socket.send.called


def test_backend_connection_send_message_serialization_failed():
    mock_serializer = mock.MagicMock()
    mock_serializer.serialize = mock.MagicMock(side_effect=NotImplementedError)
    mock_socket = mock.MagicMock()
    mock_socket.send = mock.MagicMock()

    connection = BackendConnection(mock.sentinel.SERVICE_CONFIG, mock.sentinel.LISTENERS, serializer=mock_serializer)
    connection._socket = mock_socket
    connection.state = State.Connected

    # no message is sent if serialization fails:
    connection.send_message(mock.sentinel.MESSAGE)
    assert not mock_socket.send.called


def test_backend_connection_send_message_send_failed():
    mock_serializer = mock.MagicMock()
    mock_serializer.serialize = mock.MagicMock(return_value=mock.sentinel.SERIALIZED)
    mock_socket = mock.MagicMock()
    mock_socket.send = mock.MagicMock(NotImplementedError)

    connection = BackendConnection(mock.sentinel.SERVICE_CONFIG, mock.sentinel.LISTENERS, serializer=mock_serializer)
    connection._socket = mock_socket
    connection.state = State.Connected

    # no message is sent if serialization fails, but no exception surfaces either:
    connection.send_message(mock.sentinel.MESSAGE)


def prepare_connecting_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module, now):
    mock_service_config = mock.MagicMock()
    mock_service_config.command = 'folder/somecommand.ext someparameter somethingelse'
    mock_service_config.config_file_path = path.abspath('somedir/.jep')
    mock_async_reader = mock.MagicMock()
    mock_async_reader.queue_ = queue.Queue()
    mock_provide_async_reader = mock.MagicMock(return_value=mock_async_reader)
    mock_process = mock.MagicMock()
    mock_datetime_module.datetime.now = mock.MagicMock(return_value=now)
    mock_socket_module.create_connection = mock.MagicMock()
    mock_subprocess_module.Popen = mock.MagicMock(return_value=mock_process)
    return mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config


def decorate_connection_state_dispatch(connection, delay_sec, mock_datetime_module):
    """Each dispatch of connector state takes delay_sec seconds of virtual time."""

    original_dispatch = connection._dispatch

    def _dispatch(*args):
        now = mock_datetime_module.datetime.now.return_value
        original_dispatch(*args)
        mock_datetime_module.datetime.now.return_value = now + datetime.timedelta(seconds=delay_sec)

    connection._dispatch = _dispatch


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connection_connect(mock_os_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    now = datetime.datetime.now()

    mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config = prepare_connecting_mocks(mock_datetime_module, mock_socket_module,
                                                                                                               mock_subprocess_module, now)
    connection = BackendConnection(mock_service_config, [], mock.sentinel.SERIALIZER, mock_provide_async_reader)
    connection.connect()

    # process and reader thread were started and state is adapted:
    assert mock_subprocess_module.Popen.call_args[0][0][0] == 'folder/somecommand.ext'
    assert mock_subprocess_module.Popen.call_args[1]['cwd'] == path.abspath('somedir')
    mock_async_reader.start.assert_called_once()
    assert connection.state is State.Connecting
    assert connection._process is mock_process

    # no more actions if called again:
    mock_subprocess_module.Popen.reset_mock()
    mock_provide_async_reader.reset_mock()
    connection.connect()
    assert not mock_subprocess_module.Popen.called
    assert not mock_provide_async_reader.called
    assert connection._process is mock_process

    # run state methods during "connected":
    mock_async_reader.queue_.put('Nothing special to say.')
    mock_async_reader.queue_.put('This is the JEP service, listening on port 4711. Yes really!')

    # single step as allowed duration is less than time spent in call:
    decorate_connection_state_dispatch(connection, 0.6, mock_datetime_module)
    connection.run(datetime.timedelta(seconds=0.5))

    # connection must have been created to port announced before:
    assert mock_socket_module.create_connection.called
    assert mock_socket_module.create_connection.call_args[0][0] == ('localhost', 4711)
    assert connection.state is State.Connected


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connection_connect_no_port_announcement(mock_os_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    now = datetime.datetime.now()
    mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config = prepare_connecting_mocks(mock_datetime_module, mock_socket_module,
                                                                                                               mock_subprocess_module, now)

    connection = BackendConnection(mock_service_config, [], mock.sentinel.SERIALIZER, mock_provide_async_reader)
    connection.connect()

    # run state methods during "connected":
    mock_async_reader.queue_.put('Nothing special to say.')
    mock_async_reader.queue_.put('No port announcement whatsoever.')

    assert TIMEOUT_BACKEND_STARTUP > datetime.timedelta(seconds=0)
    decorate_connection_state_dispatch(connection, 1, mock_datetime_module)

    # nothing happens within allowed timeout period:
    connection.run(TIMEOUT_BACKEND_STARTUP)
    assert connection.state is State.Connecting

    # rollback of connection after timeout has expired:
    connection.run(datetime.timedelta(seconds=2))
    assert connection.state is State.Disconnected

    mock_process.kill.assert_called_once()
    mock_async_reader.join.assert_called_once()
    assert not connection._process
    assert not connection._process_output_reader


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.time')
@mock.patch('jep.frontend.os')
def test_backend_connection_connect_connection_none(mock_os_module, mock_time_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    now = datetime.datetime.now()
    mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config = prepare_connecting_mocks(mock_datetime_module, mock_socket_module,
                                                                                                               mock_subprocess_module, now)

    connection = BackendConnection(mock_service_config, [], mock.sentinel.SERIALIZER, mock_provide_async_reader)
    connection.connect()

    # run state methods during "connected":
    mock_async_reader.queue_.put('This is the JEP service, listening on port 4711.')

    assert TIMEOUT_BACKEND_STARTUP > datetime.timedelta(seconds=0)
    decorate_connection_state_dispatch(connection, 1, mock_datetime_module)

    # fail connection return value:
    mock_socket_module.create_connection = mock.MagicMock(return_value=None)

    # nothing happens within allowed timeout period:
    connection.run(datetime.timedelta(seconds=2))
    assert connection.state is State.Disconnected

    mock_process.kill.assert_called_once()
    mock_async_reader.join.assert_called_once()
    assert not connection._process
    assert not connection._process_output_reader


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.time')
@mock.patch('jep.frontend.os')
def test_backend_connection_connect_connection_exception(mock_os_module, mock_time_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    now = datetime.datetime.now()
    mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config = prepare_connecting_mocks(mock_datetime_module, mock_socket_module,
                                                                                                               mock_subprocess_module, now)

    connection = BackendConnection(mock_service_config, [], mock.sentinel.SERIALIZER, mock_provide_async_reader)
    connection.connect()

    # run state methods during "connected":
    mock_async_reader.queue_.put('This is the JEP service, listening on port 4711.')

    assert TIMEOUT_BACKEND_STARTUP > datetime.timedelta(seconds=0)
    decorate_connection_state_dispatch(connection, 1, mock_datetime_module)

    # fail connection return value:
    mock_socket_module.create_connection = mock.MagicMock(side_effect=NotImplementedError)

    # nothing happens within allowed timeout period:
    connection.run(datetime.timedelta(seconds=2))
    assert connection.state is State.Disconnected

    mock_process.kill.assert_called_once()
    mock_async_reader.join.assert_called_once()
    assert not connection._process
    assert not connection._process_output_reader


def prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module):
    now = datetime.datetime.now()
    mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config = prepare_connecting_mocks(mock_datetime_module, mock_socket_module,
                                                                                                               mock_subprocess_module, now)
    mock_serializer = mock.MagicMock()
    mock_serializer.serialize = mock.MagicMock(return_value=mock.sentinel.SERIALIZED_SHUTDOWN)
    connection = BackendConnection(mock_service_config, [], mock_serializer, mock_provide_async_reader)
    connection.connect()
    mock_async_reader.queue_.put('This is the JEP service, listening on port 4711')
    mock_socket = mock.MagicMock()
    mock_socket_module.create_connection.return_value = mock_socket
    decorate_connection_state_dispatch(connection, 0.5, mock_datetime_module)
    connection.run(datetime.timedelta(seconds=0.4))
    assert connection.state is State.Connected
    return connection, mock_process, mock_serializer, mock_socket


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_disconnect_backend_shutdown_ok(mock_os_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    connection.disconnect()

    # frontend tried to send shutdown to connected backend:
    assert isinstance(mock_serializer.serialize.call_args[0][0], Shutdown)
    mock_socket.send.assert_called_once_with(mock.sentinel.SERIALIZED_SHUTDOWN)

    # run to wait for backend to shut down gracefully:
    mock_process.poll = mock.MagicMock(return_value=0)
    connection.run(datetime.timedelta(seconds=0.4))

    assert connection.state is State.Disconnected
    assert not connection._process
    assert not connection._process_output_reader


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.time')
@mock.patch('jep.frontend.os')
def test_backend_connected_disconnect_backend_shutdown_timeout(mock_os_module, mock_time_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    connection.disconnect()
    assert TIMEOUT_BACKEND_SHUTDOWN > datetime.timedelta(seconds=0)

    # run to wait for backend to shut down gracefully, but it won't:
    mock_process.poll = mock.MagicMock(return_value=None)
    connection.run(TIMEOUT_BACKEND_SHUTDOWN)
    assert connection.state is State.Disconnecting

    # run a bit longer and get timeout reaction:
    connection.run(datetime.timedelta(seconds=1))

    mock_socket.close.assert_called_once()
    assert connection.state is State.Disconnected
    assert not connection._socket
    assert not connection._process
    assert not connection._process_output_reader


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_no_data_until_alive_timeout(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    # prepare no data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([], [], []))

    connection.run(TIMEOUT_LAST_MESSAGE)
    assert connection.state is State.Connected

    mock_process.poll = mock.MagicMock(return_value=0)
    connection.run(datetime.timedelta(seconds=1))

    mock_socket.close.assert_called_once()
    assert connection.state is State.Disconnected
    assert not connection._socket
    assert not connection._process
    assert not connection._process_output_reader


def iterate_first_and_then(first, then):
    return itertools.chain([first], itertools.repeat(then))


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_data(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    # prepare data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([mock_socket], [], []))
    mock_socket.recv = mock.MagicMock(side_effect=iterate_first_and_then(mock.sentinel.SERIALIZED, BlockingIOError))
    mock_serializer.__iter__ = mock.Mock(return_value=iter([BackendAlive()]))

    mock_listener = mock.MagicMock()
    connection.listeners.append(mock_listener)

    # do not run into timeout leading to disconnect:
    connection.run(TIMEOUT_LAST_MESSAGE / 2)
    assert connection.state is State.Connected
    assert mock_listener.on_backend_alive.called


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_data_resets_alive_timeout(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    # prepare no data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([], [], []))

    connection.run(TIMEOUT_LAST_MESSAGE)
    assert connection.state is State.Connected

    # prepare data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([mock_socket], [], []))
    mock_socket.recv = mock.MagicMock(side_effect=iterate_first_and_then(mock.sentinel.SERIALIZED, BlockingIOError))
    mock_serializer.__iter__ = mock.Mock(return_value=iter([BackendAlive()]))

    connection.run(TIMEOUT_LAST_MESSAGE)
    assert connection.state is State.Connected


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.time')
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_data_none(mock_os_module, mock_time_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    # prepare None data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([mock_socket], [], []))
    mock_socket.recv = mock.MagicMock(return_value=None)

    connection.run(datetime.timedelta(seconds=2))

    # backend tries to reconnect:
    assert connection.state is State.Connecting


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.time')
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_data_exception(mock_os_module, mock_time_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    # prepare None data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([mock_socket], [], []))
    mock_socket.recv = mock.MagicMock(side_effect=ConnectionResetError)

    connection.run(datetime.timedelta(seconds=2))
    # backend tries to reconnect:
    assert connection.state is State.Connecting
