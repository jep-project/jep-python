from unittest import mock
import umsgpack
import pytest
from test.logconfig import configure_test_logger
from jep_py.protocol import MessageSerializer
from jep_py.schema import Shutdown, BackendAlive, ContentSync, OutOfSync, CompletionRequest, CompletionResponse, CompletionOption, SemanticType, ProblemUpdate, Problem, \
    Severity, FileProblems, CompletionInvocation, StaticSyntaxRequest, SyntaxFormatType, StaticSyntaxList, StaticSyntax


def setup_function(function):
    configure_test_logger()


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
    with mock.patch('jep_py.protocol.Message.class_by_name', lambda name: Shutdown) as mock_class_by_msgname:
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


def test_message_serializer_serialize_static_syntax_request(observable_serializer):
    packed = observable_serializer.serialize(StaticSyntaxRequest(SyntaxFormatType.textmate, ['c', 'h', 'cpp']))
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='StaticSyntaxRequest', format='textmate', fileExtensions=['c', 'h', 'cpp']))
    # TODO assert packed==...


def test_message_serializer_serialize_static_syntax_list(observable_serializer):
    packed = observable_serializer.serialize(StaticSyntaxList(SyntaxFormatType.textmate, [StaticSyntax('some.syntax', ['c', 'h', 'cpp'], 'DEFINITION')]))
    observable_serializer.packer.dumps.assert_called_once_with(
        dict(_message='StaticSyntaxList',
             format='textmate',
             syntaxes=[{'name': 'some.syntax', 'fileExtensions': ['c', 'h', 'cpp'], 'definition': 'DEFINITION'}])
    )
    # TODO assert packed==...


def test_message_serializer_serialize_completion_request(observable_serializer):
    packed = observable_serializer.serialize(CompletionRequest('thefile', 10, 17, 'thetoken'))
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='CompletionRequest', file='thefile', token='thetoken', pos=10, limit=17))
    # TODO assert packed==...


def test_message_serializer_serialize_completion_invocation(observable_serializer):
    packed = observable_serializer.serialize(CompletionInvocation('id'))
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='CompletionInvocation', extensionId='id'))
    # TODO assert packed==...


def test_message_serializer_serialize_problem_update(observable_serializer):
    msg = ProblemUpdate([FileProblems('thefile', [Problem('themsg', Severity.info, 99)], 50, 10, 20)], True)
    packed = observable_serializer.serialize(msg)
    observable_serializer.packer.dumps.assert_called_once_with(dict(_message='ProblemUpdate', partial=True, fileProblems=[
        dict(file='thefile', total=50, start=10, end=20, problems=[
            dict(message='themsg', severity='info', line=99)
        ])
    ]))
    # TODO assert packed==...


def test_message_serializer_serialize_completion_response(observable_serializer):
    msg = CompletionResponse(11, 12, True, [CompletionOption('display', 'thedescription', semantics=SemanticType.string, extensionId='theExtId'),
                                            CompletionOption('display2', 'thedescription2', semantics=SemanticType.identifier, extensionId='theExtId2')],
                             'thetoken')

    packed = observable_serializer.serialize(msg)

    expected = {
        '_message': 'CompletionResponse',
        'token': 'thetoken',
        'start': 11,
        'end': 12,
        'limitExceeded': True,
        'options': [
            {'insert': 'display', 'desc': 'thedescription', 'semantics': 'string', 'extensionId': 'theExtId'},
            {'insert': 'display2', 'desc': 'thedescription2', 'semantics': 'identifier', 'extensionId': 'theExtId2'}
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
        'limitExceeded': True,
        'options': [
            {'insert': 'insert', 'desc': 'thedescription', 'semantics': 'string', 'extensionId': 'theExtId'},
            {'insert': 'insert2', 'desc': 'thedescription2', 'semantics': 'identifier', 'extensionId': 'theExtId2'}
        ]
    }

    packed = umsgpack.packb(unpacked)

    # and use serializer without unpacker:
    serializer = MessageSerializer()

    msg = serializer.deserialize(packed)

    expected = CompletionResponse(11, 12, True, [CompletionOption('insert', 'thedescription', semantics=SemanticType.string, extensionId='theExtId'),
                                                 CompletionOption('insert2', 'thedescription2', semantics=SemanticType.identifier, extensionId='theExtId2')],
                                  'thetoken')

    # avoid implementation of eq in schema classes, so rely on correct serialization for now:
    assert serializer.serialize(msg) == serializer.serialize(expected)


def test_message_serializer_enqueue_dequeue():
    serializer = MessageSerializer()

    serializer.enque_data(serializer.serialize(CompletionResponse(1, 2, False, (), 'token')))
    serializer.enque_data(serializer.serialize(CompletionResponse(3, 4, True, (), 'token2')))

    assert serializer.buffer

    msg1 = serializer.dequeue_message()
    msg2 = serializer.dequeue_message()
    msg3 = serializer.dequeue_message()
    msg4 = serializer.dequeue_message()

    assert isinstance(msg1, CompletionResponse)
    assert msg1.token == 'token'
    assert msg1.start == 1
    assert msg1.end == 2
    assert not msg1.limitExceeded

    assert isinstance(msg2, CompletionResponse)
    assert msg2.token == 'token2'
    assert msg2.start == 3
    assert msg2.end == 4
    assert msg2.limitExceeded

    assert not msg3
    assert not msg4


def test_message_serializer_enqueue_dequeue_incomplete():
    serializer = MessageSerializer()
    packed = serializer.serialize(CompletionResponse(1, 2, False))
    assert len(packed) > 1

    for b in packed:
        assert not serializer.dequeue_message()
        serializer.enque_data([b])

    assert isinstance(serializer.dequeue_message(), CompletionResponse)
    assert not serializer.dequeue_message()


def test_message_serializer_message_iterator():
    serializer = MessageSerializer()

    serializer.enque_data(serializer.serialize(CompletionResponse(1, 2, False)))
    serializer.enque_data(serializer.serialize(CompletionResponse(3, 4, True)))

    count = 0
    for msg in serializer:
        assert isinstance(msg, CompletionResponse)
        count += 1

    assert count == 2


def test_deserialize_problem_update_ruby_backend():
    serialized = b'\x82\xacfileProblems\x91\x82\xa4file\xda\x001C:\\Users\\mthiede\\gitrepos\\jep-ruby\\demo\\test.demo\xa8problems\x91\x83\xa7message\xb5unexpected token kEND\xa8severity\xa5error\xa4line\x04\xa8_message\xadProblemUpdate'

    serializer = MessageSerializer()
    serializer.enque_data(serialized)

    message = next(iter(serializer))
    assert isinstance(message, ProblemUpdate)
    assert message.fileProblems[0].problems[0].severity is Severity.error


def test_regression_009_string_argument_without_encoding():
    serialized = b'\x83\xa8_message\xabContentSync\xa4file\xd9!D:\\Work\\jep\\test\\my.requestlogger\xa4data\xa40sdf,smndfsdf M s df jhsdkashdk  sjhdjhsjdkakdhsj'

    serializer = MessageSerializer()
    serializer.enque_data(serialized)

    message = next(iter(serializer))
    assert isinstance(message, ContentSync)


def test_descode_static_syntax_request():
    serialized = b'\x82\xa6format\xa8textmate\xa8_message\xb3StaticSyntaxRequest'

    serializer = MessageSerializer()
    serializer.enque_data(serialized)

    message = next(iter(serializer))
    assert isinstance(message, StaticSyntaxRequest)
