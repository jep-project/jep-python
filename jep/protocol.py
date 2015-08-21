import umsgpack

import io
import logging
from jep.schema import Message
from jep.serializer import serialize_to_builtins, deserialize_from_builtins

_logger = logging.getLogger(__name__)

MESSAGE_KEY = '_message'


class MessageSerializer:
    """Serialization of JEP message objects."""

    def __init__(self, packer=None):
        #: Optional packer/formatter like json or msgpack, exposing typical load/dump interface.
        self.packer = packer or umsgpack
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

        with io.BytesIO(serialized) as f:
            return self._dequeue_message_from_stream(f)

    def enque_data(self, chunk):
        """Accumulates packed data chunks until the buffer holds a complete object."""
        self.buffer.extend(chunk)

    def dequeue_message(self):
        """Returns next deserialized message in queue or None."""
        if not self.buffer:
            return None

        try:
            with io.BytesIO(self.buffer) as f:
                message = self._dequeue_message_from_stream(f)
                pos = f.tell()
                self.buffer = self.buffer[pos:]
                _logger.debug('Decoded %d bytes from stream to message %s. %d bytes left.' % (pos, message.__class__, len(self.buffer)))
            return message
        except Exception as e:
            _logger.debug('Exception during stream decode: %s' % e)
            _logger.debug('Decoding of buffer with size %d failed, data assumed incomplete.' % len(self.buffer))

    def __iter__(self):
        """Iterator over messages in data buffer."""
        msg = self.dequeue_message()
        while msg:
            yield msg
            msg = self.dequeue_message()

    def _dequeue_message_from_stream(self, f):
        """Returns next deserialized message in queue or None."""
        assert self.packer, 'Cannot unpack stream data without packer.'

        obj = self.packer.load(f)
        datatypename = obj[MESSAGE_KEY]
        message = deserialize_from_builtins(obj, Message.class_by_name(datatypename))
        return message
