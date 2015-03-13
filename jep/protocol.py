from jep.schema import Shutdown, BackendAlive, ContentSync, OutOfSync, CompletionRequest, ProblemUpdate, CompletionResponse
from jep.serializer import serialize_to_builtins, deserialize_from_builtins


class MessageSerializer:
    """Serialization of JEP message objects."""

    MESSAGE_KEY = '_message'

    # explicit map to allow class independent names in protocol:
    MESSAGE_CLASS_BY_NAME = {
        'Shutdown': Shutdown,
        'BackendAlive': BackendAlive,
        'ContentSync': ContentSync,
        'OutOfSync': OutOfSync,
        'CompletionRequest': CompletionRequest,
        'ProblemUpdate': ProblemUpdate,
        'CompletionResponse': CompletionResponse
    }

    def __init__(self, dumps=None, loads=None, class_by_msgname=None):
        assert not dumps or callable(dumps)
        assert not loads or callable(loads)
        assert not class_by_msgname or callable(class_by_msgname)

        #: Optional packer/formatter used during deserialize.
        self.loads = loads
        #: Optional packer/formatter used during serialize.
        self.dumps = dumps
        #: Callable to returning class for name in protocol.
        self.class_by_msgname = class_by_msgname or (lambda name: MessageSerializer.MESSAGE_CLASS_BY_NAME[name])

    def serialize(self, message):
        """Serialize object to builtins and then optionally apply packer."""

        serialized = serialize_to_builtins(message)
        serialized[MessageSerializer.MESSAGE_KEY] = type(message).__name__

        if self.dumps:
            serialized = self.dumps(serialized)

        return serialized

    def deserialize(self, serialized):
        """Deserialize with optional packer, then create message object from builtins."""

        if self.loads:
            serialized = self.loads(serialized)

        datatype = self.class_by_msgname(serialized[MessageSerializer.MESSAGE_KEY])
        return deserialize_from_builtins(serialized, datatype)