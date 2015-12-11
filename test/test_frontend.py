import os
from os import path
import queue
from unittest import mock
import datetime
import itertools
import pytest
from jep.config import TIMEOUT_LAST_MESSAGE
from jep.frontend import Frontend, State, BackendConnection, TIMEOUT_BACKEND_STARTUP, TIMEOUT_BACKEND_SHUTDOWN
from jep.schema import Shutdown, BackendAlive, CompletionResponse, CompletionRequest
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

    frontend = Frontend(mock.sentinel.LISTENERS, service_config_provider=mock_service_config_provider, provide_backend_connection=mock_provide_backend_connection)
    connection = frontend.get_connection(mock.sentinel.FILE_NAME)

    mock_service_config_provider.provide_for.assert_called_once_with(mock.sentinel.FILE_NAME)
    mock_provide_backend_connection.assert_called_once_with(frontend, mock_service_config, mock.sentinel.LISTENERS)
    assert mock_connection.connect.call_count == 1
    assert not mock_connection.disconnect.called
    assert connection is mock_connection


def test_provide_connected_connection_second_time_with_matching_selector_and_matching_checksum():
    mock_service_config = mock.MagicMock()
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR
    mock_service_config_provider = mock.MagicMock()
    mock_service_config_provider.provide_for = mock.MagicMock(return_value=mock_service_config)
    mock_service_config_provider.checksum = mock.MagicMock(return_value=mock.sentinel.CONFIG_CHECKSUM)

    mock_connection = mock.MagicMock()
    mock_connection.service_config.checksum = mock.sentinel.CONFIG_CHECKSUM
    mock_provide_backend_connection = mock.MagicMock(return_value=mock_connection)

    frontend = Frontend(mock.sentinel.LISTENERS, service_config_provider=mock_service_config_provider, provide_backend_connection=mock_provide_backend_connection)
    connection1 = frontend.get_connection(mock.sentinel.FILE_NAME1)
    assert mock_connection.connect.called
    mock_connection.connect.reset_mock()
    mock_connection.state = State.Connected

    connection2 = frontend.get_connection(mock.sentinel.FILE_NAME2)
    assert connection1 is connection2
    assert not mock_connection.connect.called
    assert not mock_connection.disconnect.called
    assert [mock.call.provide_for(mock.sentinel.FILE_NAME1), mock.call.provide_for(mock.sentinel.FILE_NAME2)] in mock_service_config_provider.method_calls
    assert mock_provide_backend_connection.call_count == 1


def test_provide_disconnected_connection_second_time_with_matching_selector_and_matching_checksum():
    mock_service_config = mock.MagicMock()
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR
    mock_service_config_provider = mock.MagicMock()
    mock_service_config_provider.provide_for = mock.MagicMock(return_value=mock_service_config)
    mock_service_config_provider.checksum = mock.MagicMock(return_value=mock.sentinel.CONFIG_CHECKSUM)

    mock_connection = mock.MagicMock()
    mock_connection.service_config.checksum = mock.sentinel.CONFIG_CHECKSUM
    mock_provide_backend_connection = mock.MagicMock(return_value=mock_connection)

    frontend = Frontend(mock.sentinel.LISTENERS, service_config_provider=mock_service_config_provider, provide_backend_connection=mock_provide_backend_connection)
    connection1 = frontend.get_connection(mock.sentinel.FILE_NAME1)
    assert mock_connection.connect.called
    mock_connection.connect.reset_mock()
    mock_connection.state = State.Disconnected

    connection2 = frontend.get_connection(mock.sentinel.FILE_NAME2)
    assert connection1 is connection2
    assert mock_connection.connect.called
    assert not mock_connection.disconnect.called


def test_provide_connection_second_time_with_matching_selector_and_new_checksum():
    mock_service_config = mock.MagicMock()
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR
    mock_service_config_provider = mock.MagicMock()
    mock_service_config_provider.provide_for = mock.MagicMock(return_value=mock_service_config)
    mock_service_config_provider.checksum = mock.MagicMock(return_value=mock.sentinel.CONFIG_CHECKSUM)

    mock_connection = mock.MagicMock()
    mock_connection.service_config.checksum = mock.sentinel.CONFIG_CHECKSUM
    mock_provide_backend_connection = mock.MagicMock(return_value=mock_connection)

    frontend = Frontend(mock.sentinel.LISTENERS, service_config_provider=mock_service_config_provider, provide_backend_connection=mock_provide_backend_connection)
    connection1 = frontend.get_connection(mock.sentinel.FILE_NAME1)
    assert mock_connection.connect.called
    mock_connection.reset_mock()

    # now change the checksum of the provided service configuration:
    mock_service_config2 = mock.MagicMock()
    mock_service_config2.selector = mock.sentinel.CONFIG_SELECTOR
    mock_service_config_provider.provide_for.return_value = mock_service_config2
    mock_service_config_provider.checksum.return_value = mock.sentinel.CONFIG_CHECKSUM2

    connection2 = frontend.get_connection(mock.sentinel.FILE_NAME2)

    # new connection:
    assert connection1 is connection2
    assert mock_connection.reconnect.called
    mock_connection.reconnect.assert_called_once_with(mock_service_config2)
    assert mock_provide_backend_connection.call_count == 1


def test_provide_connection_second_time_with_other_selector():
    mock_service_config = mock.MagicMock()
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR
    mock_service_config_provider = mock.MagicMock()
    mock_service_config_provider.provide_for = mock.MagicMock(return_value=mock_service_config)

    mock_connection = mock.MagicMock()
    mock_provide_backend_connection = mock.MagicMock(return_value=mock_connection)

    frontend = Frontend(mock.sentinel.LISTENERS, service_config_provider=mock_service_config_provider, provide_backend_connection=mock_provide_backend_connection)
    frontend.get_connection(mock.sentinel.FILE_NAME1)
    assert mock_connection.connect.called
    mock_connection.connect.reset_mock()

    # now change the selector of the provided service configuration:
    mock_service_config.selector = mock.sentinel.CONFIG_SELECTOR2

    frontend.get_connection(mock.sentinel.FILE_NAME2)
    assert mock_provide_backend_connection.call_count == 2


def test_backend_connection_initial_state():
    connection = BackendConnection(mock.sentinel.FRONTEND, mock.sentinel.SERVICE_CONFIG, mock.sentinel.LISTENERS)
    assert connection.state is State.Disconnected


def test_backend_connection_send_message_ok():
    mock_serializer = mock.MagicMock()
    mock_serializer.serialize = mock.MagicMock(return_value=mock.sentinel.SERIALIZED)
    mock_socket = mock.MagicMock()
    mock_socket.send = mock.MagicMock()

    connection = BackendConnection(mock.sentinel.FRONTEND, mock.sentinel.SERVICE_CONFIG, [], serializer=mock_serializer)
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

    connection = BackendConnection(mock.sentinel.FRONTEND, mock.sentinel.SERVICE_CONFIG, [], serializer=mock_serializer)
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

    connection = BackendConnection(mock.sentinel.FRONTEND, mock.sentinel.SERVICE_CONFIG, [], serializer=mock_serializer)
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

    connection = BackendConnection(mock.sentinel.FRONTEND, mock.sentinel.SERVICE_CONFIG, [], serializer=mock_serializer)
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
    # reset to unpatched module:
    mock_os_module.path = path

    mock_listener = mock.MagicMock()
    connection = BackendConnection(mock.sentinel.FRONTEND, mock_service_config, [mock_listener], serializer=mock.sentinel.SERIALIZER, provide_async_reader=mock_provide_async_reader)
    connection.connect()

    # process and reader thread were started and state is adapted:
    assert mock_subprocess_module.Popen.call_args[0][0][0] == 'folder/somecommand.ext'
    assert mock_subprocess_module.Popen.call_args[1]['cwd'] == path.abspath('somedir')
    assert mock_async_reader.start.call_count == 1
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

    mock_listener.on_connection_state_changed.assert_has_calls([mock.call(State.Disconnected, State.Connecting, connection),
                                                                mock.call(State.Connecting, State.Connected, connection)])


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connection_connect_no_port_announcement(mock_os_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    now = datetime.datetime.now()
    mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config = prepare_connecting_mocks(mock_datetime_module, mock_socket_module,
                                                                                                               mock_subprocess_module, now)

    connection = BackendConnection(mock.sentinel.FRONTEND, mock_service_config, [], serializer=mock.sentinel.SERIALIZER, provide_async_reader=mock_provide_async_reader)
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

    assert mock_process.kill.call_count == 1
    assert mock_async_reader.join.call_count == 1
    assert not connection._process
    assert not connection._process_output_reader


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connection_connect_connection_none(mock_os_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    now = datetime.datetime.now()
    mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config = prepare_connecting_mocks(mock_datetime_module, mock_socket_module,
                                                                                                               mock_subprocess_module, now)

    connection = BackendConnection(mock.sentinel.FRONTEND, mock_service_config, [], serializer=mock.sentinel.SERIALIZER, provide_async_reader=mock_provide_async_reader)
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

    assert mock_process.kill.call_count == 1
    assert mock_async_reader.join.call_count == 1
    assert not connection._process
    assert not connection._process_output_reader


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connection_connect_connection_exception(mock_os_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    now = datetime.datetime.now()
    mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config = prepare_connecting_mocks(mock_datetime_module, mock_socket_module,
                                                                                                               mock_subprocess_module, now)

    connection = BackendConnection(mock.sentinel.FRONTEND, mock_service_config, [], serializer=mock.sentinel.SERIALIZER, provide_async_reader=mock_provide_async_reader)
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

    assert mock_process.kill.call_count == 1
    assert mock_async_reader.join.call_count == 1
    assert not connection._process
    assert not connection._process_output_reader


def prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module):
    now = datetime.datetime.now()
    mock_async_reader, mock_process, mock_provide_async_reader, mock_service_config = prepare_connecting_mocks(mock_datetime_module, mock_socket_module,
                                                                                                               mock_subprocess_module, now)
    mock_serializer = mock.MagicMock()
    mock_serializer.serialize = mock.MagicMock(return_value=mock.sentinel.SERIALIZED_SHUTDOWN)
    connection = BackendConnection(mock.sentinel.FRONTEND, mock_service_config, [], serializer=mock_serializer, provide_async_reader=mock_provide_async_reader)
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
@mock.patch('jep.frontend.os')
def test_backend_connected_reconnect(mock_os_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    # reset to unpatched module:
    mock_os_module.path = path

    mock_service_config2 = mock.MagicMock()
    mock_service_config2.command = 'folder/somenewcommand.ext someparameter somethingelse'
    mock_service_config2.config_file_path = path.abspath('somenewdir/.jep')
    connection.reconnect(mock_service_config2)

    # frontend tried to send shutdown to connected backend:
    assert isinstance(mock_serializer.serialize.call_args[0][0], Shutdown)
    mock_socket.send.assert_called_once_with(mock.sentinel.SERIALIZED_SHUTDOWN)

    # run to wait for backend to shut down gracefully:
    mock_process.poll = mock.MagicMock(return_value=0)
    connection.run(datetime.timedelta(seconds=0.4))

    assert connection.state is State.Connecting
    assert mock_subprocess_module.Popen.call_args[0][0][0] == 'folder/somenewcommand.ext'
    assert mock_subprocess_module.Popen.call_args[1]['cwd'] == path.abspath('somenewdir')


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_disconnect_backend_shutdown_timeout(mock_os_module, mock_datetime_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    connection.disconnect()
    assert TIMEOUT_BACKEND_SHUTDOWN > datetime.timedelta(seconds=0)

    # run to wait for backend to shut down gracefully, but it won't:
    mock_process.poll = mock.MagicMock(return_value=None)
    connection.run(TIMEOUT_BACKEND_SHUTDOWN)
    assert connection.state is State.Disconnecting

    # run a bit longer and get timeout reaction:
    connection.run(datetime.timedelta(seconds=1))

    assert mock_socket.close.call_count == 1
    assert connection.state is State.Disconnected
    assert not connection._socket
    assert not connection._process
    assert not connection._process_output_reader


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_no_data_until_alive_timeout_and_reconnect(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    # prepare no data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([], [], []))

    connection.run(TIMEOUT_LAST_MESSAGE)
    assert connection.state is State.Connected

    mock_process.poll = mock.MagicMock(return_value=0)
    connection.run(datetime.timedelta(seconds=1))

    assert mock_socket.close.call_count == 1
    assert connection.state is State.Connecting
    assert not connection._socket
    assert connection._process
    assert connection._process_output_reader


def iterate_first_and_then(first, then):
    return itertools.chain([first], itertools.repeat(then))


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_data(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)
    connection.frontend = mock.MagicMock()

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
    assert connection.frontend.on_backend_alive.called


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_data_resets_alive_timeout(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)
    connection.frontend = mock.MagicMock()

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
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_data_none(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
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
@mock.patch('jep.frontend.os')
def test_backend_connected_receive_data_exception(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    # prepare None data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([mock_socket], [], []))
    mock_socket.recv = mock.MagicMock(side_effect=ConnectionResetError)

    connection.run(datetime.timedelta(seconds=2))
    # backend tries to reconnect:
    assert connection.state is State.Connecting


def test_backend_connection_request_message_no_token_attribute():
    connection = BackendConnection(mock.sentinel.FRONTEND, mock.sentinel.SERVICE_CONFIG, [])
    connection.state = State.Connected
    with pytest.raises(AttributeError):
        connection.request_message(Shutdown(), mock.sentinel.DURATION)


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_run_for_duration(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)

    # prepare no data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([], [], []))

    decorate_connection_state_dispatch(connection, 0.1, mock_datetime_module)
    now = mock_datetime_module.datetime.now()
    connection.run(datetime.timedelta(seconds=1))

    # without anything happening, the connection was simply run for the whole duration:
    assert mock_datetime_module.datetime.now() == now + datetime.timedelta(seconds=1)


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_run_without_response_received(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)
    connection.frontend = mock.MagicMock()

    # set internal token of request:
    connection._current_request_token = mock.sentinel.TOKEN
    connection._current_request_response = None

    # prepare no data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([], [], []))

    decorate_connection_state_dispatch(connection, 0.1, mock_datetime_module)
    now = mock_datetime_module.datetime.now()
    connection.run(datetime.timedelta(seconds=1))

    # also when waiting for response (and it's not coming) the connection is run for the complete duration:
    assert mock_datetime_module.datetime.now() == now + datetime.timedelta(seconds=1)


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_run_wit__other_response_received(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)
    connection.frontend = mock.MagicMock()

    # set internal token of request:
    connection._current_request_token = mock.sentinel.TOKEN
    connection._current_request_response = None

    # prepare data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([mock_socket], [], []))
    mock_socket.recv = mock.MagicMock(side_effect=iterate_first_and_then(mock.sentinel.SERIALIZED, BlockingIOError))
    mock_serializer.__iter__ = mock.Mock(return_value=iter([CompletionResponse(0, 1, token=mock.sentinel.OTHER_TOKEN)]))

    decorate_connection_state_dispatch(connection, 0.1, mock_datetime_module)
    now = mock_datetime_module.datetime.now()
    connection.run(datetime.timedelta(seconds=1))

    # also when waiting for response (and it's not coming) the connection is run for the complete duration:
    assert mock_datetime_module.datetime.now() == now + datetime.timedelta(seconds=1)


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_run_with_response_received(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)
    connection.frontend = mock.MagicMock()

    # set internal token of request:
    connection._current_request_token = mock.sentinel.TOKEN
    connection._current_request_response = None

    # prepare data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([mock_socket], [], []))
    mock_socket.recv = mock.MagicMock(side_effect=iterate_first_and_then(mock.sentinel.SERIALIZED, BlockingIOError))
    mock_serializer.__iter__ = mock.Mock(return_value=iter([CompletionResponse(0, 1, token=mock.sentinel.TOKEN)]))

    decorate_connection_state_dispatch(connection, 0.1, mock_datetime_module)
    now = mock_datetime_module.datetime.now()
    connection.run(datetime.timedelta(seconds=1))

    # run returns immediately if the correctly tokenized message is received:
    assert mock_datetime_module.datetime.now() == now + datetime.timedelta(seconds=0.1)


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_request_message_without_response(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)
    connection.frontend = mock.MagicMock()

    # prepare no data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([], [], []))

    request = CompletionRequest('file', 0)

    decorate_connection_state_dispatch(connection, 0.1, mock_datetime_module)
    now = mock_datetime_module.datetime.now()
    connection.request_message(request, datetime.timedelta(seconds=1))

    assert request.token is not None

    # make sure request was sent:
    mock_serializer.serialize.assert_called_once_with(request)

    # when waiting for response (and it's not coming) the connection is run for the complete duration:
    assert mock_datetime_module.datetime.now() == now + datetime.timedelta(seconds=1)


@mock.patch('jep.frontend.subprocess')
@mock.patch('jep.frontend.socket')
@mock.patch('jep.frontend.select')
@mock.patch('jep.frontend.datetime')
@mock.patch('jep.frontend.os')
def test_backend_connected_request_message_with_response(mock_os_module, mock_datetime_module, mock_select_module, mock_socket_module, mock_subprocess_module):
    connection, mock_process, mock_serializer, mock_socket = prepare_connected_mocks(mock_datetime_module, mock_socket_module, mock_subprocess_module)
    connection.frontend = mock.MagicMock()

    # prepare data ready for reception:
    mock_select_module.select = mock.MagicMock(return_value=([mock_socket], [], []))
    mock_socket.recv = mock.MagicMock(side_effect=iterate_first_and_then(mock.sentinel.SERIALIZED, BlockingIOError))
    mock_serializer.__iter__ = mock.Mock(return_value=iter([CompletionResponse(0, 1, token=mock.sentinel.TOKEN)]))

    request = CompletionRequest('file', 0, token=mock.sentinel.TOKEN)

    decorate_connection_state_dispatch(connection, 0.1, mock_datetime_module)
    now = mock_datetime_module.datetime.now()
    connection.request_message(request, datetime.timedelta(seconds=1))

    # synchronous call returns immediately upon reception of response with correct token:
    assert mock_datetime_module.datetime.now() == now + datetime.timedelta(seconds=0.1)
