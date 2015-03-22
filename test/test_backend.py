"""Tests of backend features (no integration with frontend)."""
from unittest import mock
import pytest
from jep.backend import Backend, State, NoPortFoundError, PORT_RANGE, FrontendConnector
from jep.protocol import MessageSerializer
from jep.schema import Shutdown, BackendAlive


def test_initial_state():
    backend = Backend()
    assert not backend.serversocket
    assert backend.state is State.Stopped


@mock.patch('jep.backend.socket')
def test_find_server_port(mock_socket_mod):
    # deny binding to any port:
    mock_socket_mod.socket().bind = mock.MagicMock(side_effect=OSError)
    backend = Backend()

    with pytest.raises(NoPortFoundError):
        backend.start()

    assert PORT_RANGE[0] < PORT_RANGE[1], 'At lest one port should be testable.'

    # check if all ports have been tested:
    for port in range(PORT_RANGE[0], PORT_RANGE[1]):
        assert mock.call(('localhost', port)) in mock_socket_mod.socket().bind.call_args_list

    assert backend.state is State.Stopped


def set_backend_state(backend, state, return_value=None):
    """Utility to set backend state from outside as mock side-effect."""

    def _(*args):
        backend.state = state
        return return_value

    return _


@mock.patch('jep.backend.socket')
@mock.patch('jep.backend.select')
def test_bind_and_listen_and_accept_and_disconnect(mock_select_mod, mock_socket_mod, capsys):
    backend = Backend()
    server_socket = mock_socket_mod.socket()

    # mock a connecting frontend:
    mock_select_mod.select = mock.MagicMock(return_value=([server_socket], [], []))
    client_socket = mock.MagicMock()
    server_socket.accept = mock.MagicMock(side_effect=set_backend_state(backend, State.ShutdownPending, [client_socket]))
    backend.start()
    assert backend.state is State.Stopped
    server_socket.close.assert_called_once()
    client_socket.close.assert_called_once()

    out, *_ = capsys.readouterr()
    assert 'JEP service, listening on port 9001' in out


def test_receive_shutdown():
    mock_clientsocket = mock.MagicMock()
    mock_clientsocket.recv = mock.MagicMock(return_value=MessageSerializer().serialize(Shutdown()))
    mock_listener1 = mock.MagicMock()
    mock_listener2 = mock.MagicMock()
    backend = Backend([mock_listener1, mock_listener2])
    backend.frontend_by_socket[mock_clientsocket] = FrontendConnector()

    assert backend.state is not State.ShutdownPending
    backend._receive(mock_clientsocket)

    # listeners are called:
    assert isinstance(mock_listener1.on_message_received.call_args[0][0], Shutdown)
    assert isinstance(mock_listener2.on_message_received.call_args[0][0], Shutdown)

    # backend reacted to shutdown:
    assert backend.state is State.ShutdownPending


def test_message_context():
    mock_clientsocket = mock.MagicMock()
    mock_clientsocket.recv = mock.MagicMock(return_value=MessageSerializer().serialize(Shutdown()))
    mock_listener = mock.MagicMock()
    backend = Backend([mock_listener])
    backend.frontend_by_socket[mock_clientsocket] = FrontendConnector()

    backend._receive(mock_clientsocket)
    message_context = mock_listener.on_message_received.call_args[0][1]
    assert message_context.service is backend
    assert message_context.sock is mock_clientsocket

    message_context.send_message(BackendAlive())
    assert mock_clientsocket.send.call_count == 1
