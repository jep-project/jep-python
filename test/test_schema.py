from jep.schema import Message, Shutdown, CompletionResponse


def test_message_class_by_name():
    assert Message.class_by_name('Shutdown') is Shutdown
    assert Message.class_by_name('CompletionResponse') is CompletionResponse
