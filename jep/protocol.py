import logging
import jep.contrib.umsgpack as umsgpack
from jep.schema import Shutdown, BackendAlive, ContentSync, OutOfSync, CompletionRequest, ProblemUpdate, CompletionResponse
from jep.serializer import serialize_to_builtins, deserialize_from_builtins

_logger = logging.getLogger(__name__)


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
        self.loads = loads or umsgpack.loads
        #: Optional packer/formatter used during serialize.
        self.dumps = dumps or umsgpack.dumps
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
