"""Test of content synchronization of KEP backend."""
from unittest import mock
from jep.backend import Backend, FrontendConnection
from jep.protocol import MessageSerializer
from jep.schema import ContentSync, OutOfSync


# def test_propagate_content_sync():
#     mock_clientsocket = mock.MagicMock()
#     mock_clientsocket.recv = mock.MagicMock(side_effect=[MessageSerializer().serialize(ContentSync('/path/to/file', 'new content', 17, 21)), BlockingIOError])
#     mock_listener = mock.MagicMock()
#     backend = Backend([mock_listener])
#     backend.connection[mock_clientsocket] = FrontendConnection(backend, mock_clientsocket)
#
#     backend._receive(mock_clientsocket)
#
#     # listeners are called:
#     mock_listener.on_content_sync.assert_called_once()
#     mock_service_handler.on_content_sync.assert_called_once()
#
#     arg = mock_service_handler.on_content_sync.call_args[0][0]
#     assert isinstance(arg, ContentSync)
#     assert arg.file == '/path/to/file'
#     assert arg.data == 'new content'
#     assert arg.start == 17
#     assert arg.end == 21
#
#
# def test_content_accessor():
#     mock_service_handler = mock.MagicMock()
#     backend = Backend(service_handler=mock_service_handler)
#     assert backend.content_by_filepath is mock_service_handler.content_by_filepath
#
#
# def test_content_sync_initial_state():
#     handler = ServiceHandler()
#     assert '/path/to/file' not in handler.content_by_filepath
#     assert handler.content_by_filepath['/new/file'] == ''
#
#
# def test_content_sync_initial_sync():
#     sync = ContentSync('/path/to/file', 'new content', 0, 0)
#     mock_context = mock.MagicMock()
#     mock_context.send_message = mock.MagicMock()
#     handler = ServiceHandler()
#
#     handler.on_content_sync(sync, mock_context)
#
#     assert handler.content_by_filepath['/path/to/file'] == 'new content'
#     assert not mock_context.send_message.called
#
#
# def test_content_sync_out_of_sync():
#     sync = ContentSync('/path/to/file', 'new content', 17, 21)
#     mock_context = mock.MagicMock()
#     mock_context.send_message = mock.MagicMock()
#     handler = ServiceHandler()
#     handler.on_content_sync(sync, mock_context)
#
#     assert handler.content_by_filepath['/path/to/file'] == ''
#     arg = mock_context.send_message.call_args[0][0]
#     assert isinstance(arg, OutOfSync)
#     assert arg.file == '/path/to/file'