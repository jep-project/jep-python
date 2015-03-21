try:
    import umsgpack
except ImportError:
    from jep.contrib import umsgpack

import io
import logging
from jep.schema import Shutdown, BackendAlive, ContentSync, OutOfSync, CompletionRequest, ProblemUpdate, CompletionResponse
from jep.serializer import serialize_to_builtins, deserialize_from_builtins

_logger = logging.getLogger(__name__)

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


class MessageSerializer:
    """Serialization of JEP message objects."""

    def __init__(self, packer=umsgpack):
        #: Optional packer/formatter like json or msgpack, exposing typical load/dump interface.
        self.packer = packer
        #: Buffer holding chunked data (mutable).
        self.buffer = bytearray()

    def serialize(self, message):
        """Serialize object to builtins and then optionally apply packer."""

        serialized = serialize_to_builtins(message)
        serialized[MESSAGE_KEY] = type(message).__name__

        if self.packer:
            serialized = self.packer.dumps(serialized)

        return serialized

    def deserialize(self, serialized):
        """Deserialize with optional packer, then create message object from builtins."""

        if self.packer:
            serialized = self.packer.loads(serialized)

        datatype = MESSAGE_CLASS_BY_NAME[(serialized[MESSAGE_KEY])]
        return deserialize_from_builtins(serialized, datatype)

    def enqueue_data(self, chunk):
        """Accumulates data chunks until the buffer holds a complete object."""
        self.buffer.extend(chunk)

    def dequeue_message(self):
        """Returns next deserialized message in queue or None."""
        if not self.buffer:
            return None

        try:
            f = io.BytesIO(self.buffer)
        except:
            pass

