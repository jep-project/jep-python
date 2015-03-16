from unittest import mock
import pytest
import jep.contrib.umsgpack as umsgpack
from jep.protocol import MessageSerializer, JepProtocolMixin
from jep.schema import Shutdown, BackendAlive, ContentSync, OutOfSync, CompletionRequest, CompletionResponse, CompletionOption, SemanticType, ProblemUpdate, Problem, \
    Severity, FileProblems


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


def test_message_serializer_serialize_completion_request(observable_serializer):
    packed = observable_serializer.serialize(CompletionRequest('thetoken', 'thefile', 10, 17))
    observable_serializer.dumps.assert_called_once_with(dict(_message='CompletionRequest', file='thefile', token='thetoken', pos=10, limit=17))
    # TODO assert packed==...


def test_message_serializer_serialize_problem_update(observable_serializer):
    msg = ProblemUpdate([FileProblems('thefile', [Problem('themsg', Severity.Info, 99)], 50, 10, 20)], True)
    packed = observable_serializer.serialize(msg)
    observable_serializer.dumps.assert_called_once_with(dict(_message='ProblemUpdate', partial=True, file_problems=[
        dict(file='thefile', total=50, start=10, end=20, problems=[
            dict(message='themsg', severity='Info', line=99)
        ])
    ]))
    # TODO assert packed==...


def test_message_serializer_serialize_completion_response(observable_serializer):
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


def test_message_serializer_deserialize_completion_response():
    # TODO should start with a packed message and use msgpack to unpack, for now start with builtin form:
    unpacked = {
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

    # and use serializer without unpacker:
    serializer = MessageSerializer(dumps=lambda s: s, loads=lambda s: s)

    msg = serializer.deserialize(unpacked)

    expected = CompletionResponse('thetoken', 11, 12, True, [CompletionOption('display', 'thedescription', SemanticType.String, 'theExtId'),
                                                             CompletionOption('display2', 'thedescription2', SemanticType.Identifier, 'theExtId2')])

    # avoid implementation of eq in schema classes, so rely on correct serialization for now:
    assert serializer.serialize(msg) == serializer.serialize(expected)


def test_protocl_mixin_subscription():
    mock_listener = mock.MagicMock()
    protocol = JepProtocolMixin(listener=mock_listener)
    assert protocol.listener is mock_listener
    assert mock_listener.protocol is protocol


def test_protocol_mixin_on_data_received():
    mock_serializer = mock.MagicMock()
    mock_serializer.deserialize = mock.MagicMock(return_value=mock.sentinel.DESERIALIZED)
    mock_listener = mock.MagicMock()

    p = JepProtocolMixin(mock_listener, mock_serializer)
    p._on_data_received(mock.sentinel.SERIALIZED)

    mock_serializer.deserialize.assert_called_once_with(mock.sentinel.SERIALIZED)
    mock_listener.on_message_received.assert_called_once_with(mock.sentinel.DESERIALIZED)


def test_protocol_mixin_send_message():
    mock_serializer = mock.MagicMock()
    mock_serializer.serialize = mock.MagicMock(return_value=mock.sentinel.SERIALIZED)

    with mock.patch('test_protocol.JepProtocolMixin._send_data') as mock_send_data:
        p = JepProtocolMixin(serializer=mock_serializer)
        p.send_message(mock.sentinel.MESSAGE)

        mock_serializer.serialize.assert_called_once_with(mock.sentinel.MESSAGE)
        mock_send_data.assert_called_once_woth(mock.sentinel.SERIALIZED)


def test_protocol_mixin_connection_state():
    mock_listener = mock.MagicMock()
    p = JepProtocolMixin(listener=mock_listener)

    p._on_connection_made()
    p._on_connection_lost()

    assert mock_listener.method_calls == [mock.call.on_connection_made(), mock.call.on_connection_lost()]
