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


class JepProtocolMixin:
    """Framework independent implementation of JEP protocol, exposing a message oriented interface."""

    def __init__(self, listener=None, serializer=None):
        #: Listener called for received messages.
        self.listener = listener
        self.serializer = serializer or MessageSerializer()

        # register protocol with listener:
        if listener:
            listener.protocol = self

    def send_message(self, message):
        _logger.debug('Protocol sends message: %s.' % message)
        serialized = self.serializer.serialize(message)
        self._send_data(serialized)

    @property
    def connected(self):
        raise NotImplementedError()

    def _send_data(self, data):
        """To be implemented specific for used framework."""
        raise NotImplementedError()

    def _on_data_received(self, data):
        """Received data is encoded and passed to message listener."""
        message = self.serializer.deserialize(data)
        _logger.debug('Protocol received message: %s.' % message)
        if self.listener:
            self.listener.on_message_received(message)

    def _on_connection_made(self):
        _logger.debug('Protocol connected.')
        if self.listener:
            self.listener.on_connection_made()

    def _on_connection_lost(self):
        _logger.debug('Protocol disconnected.')
        if self.listener:
            self.listener.on_connection_lost()


class JepProtocolListener:
    protocol = None

    def on_message_received(self, message):
        pass

    def on_connection_made(self):
        pass

    def on_connection_lost(self):
        pass
