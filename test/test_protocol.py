from unittest import mock
import pytest
import umsgpack
from jep.protocol import MessageSerializer
from jep.schema import Shutdown, BackendAlive, ContentSync, OutOfSync, CompletionRequest, CompletionResponse, CompletionOption, SemanticType


def test_message_serializer_serialize_chain():
    mock_dumps = mock.MagicMock(return_value=mock.sentinel.PACKER_RESULT)
    serializer = MessageSerializer(dumps=mock_dumps)

    # make sure packer is called and its result is returned:
    assert serializer.serialize(Shutdown()) == mock.sentinel.PACKER_RESULT
    mock_dumps.assert_called_once_with(dict(_message='Shutdown'))


def test_message_serializer_deserialize_chain():
    mock_loads = mock.MagicMock(return_value=dict(_message=mock.sentinel.MESSAGE_NAME))
    mock_class_by_msgname = mock.MagicMock(return_value=Shutdown)
    serializer = MessageSerializer(loads=mock_loads, class_by_msgname=mock_class_by_msgname)

    assert isinstance(serializer.deserialize(mock.sentinel.PACKER_RESULT), Shutdown)
    mock_loads.assert_called_once_with(mock.sentinel.PACKER_RESULT)
    mock_class_by_msgname.assert_called_once_with(mock.sentinel.MESSAGE_NAME)


@pytest.fixture
def observable_serializer():
    """Provides message serializer to test with msgpack installed via observable mocks."""
    mock_loads = mock.MagicMock(side_effect=lambda bindata: umsgpack.loads(bindata))
    mock_dumps = mock.MagicMock(side_effect=lambda pydict: umsgpack.dumps(pydict))
    return MessageSerializer(mock_dumps, mock_loads)


def test_message_serializer_serialize_shutdown(observable_serializer):
    packed = observable_serializer.serialize(Shutdown())
    observable_serializer.dumps.assert_called_once_with(dict(_message='Shutdown'))
    # TODO assert packed==...


def test_message_serializer_serialize_backend_alive(observable_serializer):
    packed = observable_serializer.serialize(BackendAlive())
    observable_serializer.dumps.assert_called_once_with(dict(_message='BackendAlive'))
    # TODO assert packed==...


def test_message_serializer_serialize_content_sync(observable_serializer):
    packed = observable_serializer.serialize(ContentSync('thefile', bytes('thedata', 'utf-8'), 9, 11))
    observable_serializer.dumps.assert_called_once_with(dict(_message='ContentSync', start=9, end=11, data=bytes('thedata', 'utf-8'), file='thefile'))
    # TODO assert packed==...


def test_message_serializer_serialize_out_of_sync(observable_serializer):
    packed = observable_serializer.serialize(OutOfSync('thefile'))
    observable_serializer.dumps.assert_called_once_with(dict(_message='OutOfSync', file='thefile'))
    # TODO assert packed==...


def test_message_serializer_completion_request(observable_serializer):
    packed = observable_serializer.serialize(CompletionRequest('thetoken', 'thefile', 10, 17))
    observable_serializer.dumps.assert_called_once_with(dict(_message='CompletionRequest', file='thefile', token='thetoken', pos=10, limit=17))
    # TODO assert packed==...


def test_message_serializer_completion_response(observable_serializer):
    msg = CompletionResponse('thetoken', 11, 12, True, [CompletionOption('display', 'thedescription', SemanticType.String, 'theExtId'),
                                                        CompletionOption('display2', 'thedescription2', SemanticType.Identifier, 'theExtId2')])

    packed = observable_serializer.serialize(msg)

    expected = {
        '_message': 'CompletionResponse',
        'token': 'thetoken',
        'start': 11,
        'end': 12,
        'limit_exceeded': True,
        'options': [
            {'display': 'display', 'desc': 'thedescription', 'semantics': 'String', 'extension_id': 'theExtId'},
            {'display': 'display2', 'desc': 'thedescription2', 'semantics': 'Identifier', 'extension_id': 'theExtId2'}
        ]
    }
    observable_serializer.dumps.assert_called_once_with(expected)
    # TODO assert packed==...
