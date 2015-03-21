try:
    import umsgpack
except ImportError:
    from jep.contrib import umsgpack

from unittest import mock
import pytest
from jep.protocol import MessageSerializer
from jep.schema import Shutdown, BackendAlive, ContentSync, OutOfSync, CompletionRequest, CompletionResponse, CompletionOption, SemanticType, ProblemUpdate, Problem, \
    Severity, FileProblems


def test_message_serializer_serialize_chain():
    mock_packer = mock.MagicMock()
    mock_packer.dumps = mock.MagicMock(return_value=mock.sentinel.PACKER_RESULT)
    serializer = MessageSerializer(mock_packer)

    # make sure packer is called and its result is returned:
    assert serializer.serialize(Shutdown()) == mock.sentinel.PACKER_RESULT
    mock_packer.dumps.assert_called_once_with(dict(_message='Shutdown'))


def test_message_serializer_deserialize_chain():
    mock_packer = mock.MagicMock()
    mock_packer.loads = mock.MagicMock(return_value=dict(_message=mock.sentinel.MESSAGE_NAME))
    with mock.patch('jep.protocol.MESSAGE_CLASS_BY_NAME', {mock.sentinel.MESSAGE_NAME: Shutdown}) as mock_class_by_msgname:
        serializer = MessageSerializer(mock_packer)
        assert isinstance(serializer.deserialize(mock.sentinel.PACKER_RESULT), Shutdown)
        mock_packer.loads.assert_called_once_with(mock.sentinel.PACKER_RESULT)


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

    # and use serializer without unpacker:
    serializer = MessageSerializer(packer=None)

    msg = serializer.deserialize(unpacked)

    expected = CompletionResponse('thetoken', 11, 12, True, [CompletionOption('display', 'thedescription', SemanticType.String, 'theExtId'),
                                                             CompletionOption('display2', 'thedescription2', SemanticType.Identifier, 'theExtId2')])

    # avoid implementation of eq in schema classes, so rely on correct serialization for now:
    assert serializer.serialize(msg) == serializer.serialize(expected)
