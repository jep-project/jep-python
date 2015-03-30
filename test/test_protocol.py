try:
    import umsgpack
except ImportError:
    from jep.contrib import umsgpack

from unittest import mock
import pytest
from jep.protocol import MessageSerializer
from jep.schema import Shutdown, BackendAlive, ContentSync, OutOfSync, CompletionRequest, CompletionResponse, CompletionOption, SemanticType, ProblemUpdate, Problem, \
    Severity, FileProblems, CompletionInvocation


def test_message_serializer_serialize_chain():
    mock_packer = mock.MagicMock()
    mock_packer.dumps = mock.MagicMock(return_value=mock.sentinel.PACKER_RESULT)
    serializer = MessageSerializer(mock_packer)

    # make sure packer is called and its result is returned:
    assert serializer.serialize(Shutdown()) == mock.sentinel.PACKER_RESULT
    mock_packer.dumps.assert_called_once_with(dict(_message='Shutdown'))


def test_message_serializer_deserialize_chain():
    mock_packer = mock.MagicMock()
    mock_packer.load = mock.MagicMock(return_value=dict(_message=mock.sentinel.MESSAGE_NAME))
    buffer = bytes(b'bytes')
    with mock.patch('jep.protocol.MESSAGE_CLASS_BY_NAME', {mock.sentinel.MESSAGE_NAME: Shutdown}) as mock_class_by_msgname:
        serializer = MessageSerializer(mock_packer)
        assert isinstance(serializer.deserialize(buffer), Shutdown)
        assert mock_packer.load.called


@pytest.fixture
def observable_serializer():
    """Provides message serializer to test with msgpack installed via observable mocks."""
    mock_packer = mock.MagicMock()
    mock_packer.loads = mock.MagicMock(side_effect=lambda bindata: umsgpack.loads(bindata))
    mock_packer.dumps = mock.MagicMock(side_effect=lambda pydict: umsgpack.dumps(pydict))
    return MessageSerializer(mock_packer)


def test_message_serializer_serialize_shutdown(observable_serializer):
    packed = observable_serializer.serialize(Shutdown())
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='Shutdown'))
    # TODO assert packed==...


def test_message_serializer_serialize_backend_alive(observable_serializer):
    packed = observable_serializer.serialize(BackendAlive())
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='BackendAlive'))
    # TODO assert packed==...


def test_message_serializer_serialize_content_sync(observable_serializer):
    packed = observable_serializer.serialize(ContentSync('thefile', bytes('thedata', 'utf-8'), 9, 11))
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='ContentSync', start=9, end=11, data=bytes('thedata', 'utf-8'), file='thefile'))
    # TODO assert packed==...


def test_message_serializer_serialize_out_of_sync(observable_serializer):
    packed = observable_serializer.serialize(OutOfSync('thefile'))
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='OutOfSync', file='thefile'))
    # TODO assert packed==...


def test_message_serializer_serialize_completion_request(observable_serializer):
    packed = observable_serializer.serialize(CompletionRequest('thetoken', 'thefile', 10, 17))
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='CompletionRequest', file='thefile', token='thetoken', pos=10, limit=17))
    # TODO assert packed==...


def test_message_serializer_serialize_completion_invocation(observable_serializer):
    packed = observable_serializer.serialize(CompletionInvocation('id'))
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='CompletionInvocation', extension_id='id'))
    # TODO assert packed==...


def test_message_serializer_serialize_problem_update(observable_serializer):
    msg = ProblemUpdate([FileProblems('thefile', [Problem('themsg', Severity.Info, 99)], 50, 10, 20)], True)
    packed = observable_serializer.serialize(msg)
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='ProblemUpdate', partial=True, file_problems=[
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
    observable_serializer.packer.dumps.assert_called_once_with(expected)
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

    packed = umsgpack.packb(unpacked)

    # and use serializer without unpacker:
    serializer = MessageSerializer()

    msg = serializer.deserialize(packed)

    expected = CompletionResponse('thetoken', 11, 12, True, [CompletionOption('display', 'thedescription', SemanticType.String, 'theExtId'),
                                                             CompletionOption('display2', 'thedescription2', SemanticType.Identifier, 'theExtId2')])

    # avoid implementation of eq in schema classes, so rely on correct serialization for now:
    assert serializer.serialize(msg) == serializer.serialize(expected)


def test_message_serializer_enqueue_dequeue():
    serializer = MessageSerializer()

    serializer.enque_data(serializer.serialize(CompletionResponse('token', 1, 2, False)))
    serializer.enque_data(serializer.serialize(CompletionResponse('token2', 3, 4, True)))

    assert serializer.buffer

    msg1 = serializer.dequeue_message()
    msg2 = serializer.dequeue_message()
    msg3 = serializer.dequeue_message()
    msg4 = serializer.dequeue_message()

    assert isinstance(msg1, CompletionResponse)
    assert msg1.token == 'token'
    assert msg1.start == 1
    assert msg1.end == 2
    assert not msg1.limit_exceeded

    assert isinstance(msg2, CompletionResponse)
    assert msg2.token == 'token2'
    assert msg2.start == 3
    assert msg2.end == 4
    assert msg2.limit_exceeded

    assert not msg3
    assert not msg4


def test_message_serializer_enqueue_dequeue_incomplete():
    serializer = MessageSerializer()
    packed = serializer.serialize(CompletionResponse('token', 1, 2, False))
    assert len(packed) > 1

    for b in packed:
        assert not serializer.dequeue_message()
        serializer.enque_data([b])

    assert isinstance(serializer.dequeue_message(), CompletionResponse)
    assert not serializer.dequeue_message()


def test_message_serializer_message_iterator():
    serializer = MessageSerializer()

    serializer.enque_data(serializer.serialize(CompletionResponse('token', 1, 2, False)))
    serializer.enque_data(serializer.serialize(CompletionResponse('token2', 3, 4, True)))

    count = 0
    for msg in serializer:
        assert isinstance(msg, CompletionResponse)
        count += 1

    assert count == 2