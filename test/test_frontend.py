import os
from unittest import mock
from jep.frontend import Frontend, State, BackendConnection


def setup_function(function):
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
    mock_connection.connect.reset_mock()

    # now change the checksum of the provided service configuration:
    mock_service_config_provider.checksum = mock.MagicMock(return_value=mock.sentinel.CONFIG_CHECKSUM2)

    connection2 = frontend.get_connection(mock.sentinel.FILE_NAME2)

    # still the same connection, but reconnected due to checksum change:
    assert connection1 is connection2
    assert mock_connection.method_calls == [mock.call.connect(), mock.call.disconnect(), mock.call.connect()]
    assert mock_provide_backend_connection.call_count == 1


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
