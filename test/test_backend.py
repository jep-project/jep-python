"""Tests of backend features (no integration with frontend)."""
from unittest import mock
import datetime
import pytest
from jep.backend import Backend, State, NoPortFoundError, PORT_RANGE, FrontendConnector, TIMEOUT_BACKEND_ALIVE
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


def test_receive_empty():
    mock_clientsocket = mock.MagicMock()
    mock_clientsocket.recv = mock.MagicMock(return_value=None)
    backend = Backend()
    backend.frontend_by_socket[mock_clientsocket] = FrontendConnector()
    backend.sockets.append(mock_clientsocket)

    backend._receive(mock_clientsocket)
    mock_clientsocket.close.assert_called_once()


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


@mock.patch('jep.backend.datetime')
def test_backend_alive_cycle(mock_datetime_mod):
    now = datetime.datetime.now()
    mock_datetime_mod.datetime.now = mock.MagicMock(side_effect=lambda: now)

    mock_clientsocket1 = mock.MagicMock()
    mock_clientsocket2 = mock.MagicMock()
    backend = Backend()
    backend.sockets = [mock.sentinel.SERVER_SOCKET, mock_clientsocket1, mock_clientsocket2]
    backend.frontend_by_socket[mock_clientsocket1] = FrontendConnector()
    backend.frontend_by_socket[mock_clientsocket2] = FrontendConnector()

    # cycle must send alive for all newly connected frontends:
    backend._cyclic()
    assert b'BackendAlive' in mock_clientsocket1.send.call_args[0][0]
    assert b'BackendAlive' in mock_clientsocket2.send.call_args[0][0]

    # no new alive message before timeout has expired:
    assert TIMEOUT_BACKEND_ALIVE > datetime.timedelta(0)
    now += TIMEOUT_BACKEND_ALIVE * 0.9
    mock_clientsocket1.send.reset_mock()
    mock_clientsocket2.send.reset_mock()
    backend._cyclic()
    assert not mock_clientsocket1.called
    assert not mock_clientsocket2.called

    # but right after:
    now += TIMEOUT_BACKEND_ALIVE * 0.15
    mock_clientsocket1.send.reset_mock()
    mock_clientsocket2.send.reset_mock()
    backend._cyclic()
    assert b'BackendAlive' in mock_clientsocket1.send.call_args[0][0]
    assert b'BackendAlive' in mock_clientsocket2.send.call_args[0][0]
