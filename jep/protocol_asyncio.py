"""Asyncio specific implementation of JEP protocol."""
import asyncio
from jep.protocol import ProtocolMixin


class Protocol(asyncio.Protocol, ProtocolMixin):
    """Asyncio protocol for JEP, connecting asyncio and framework independent mixin."""

    transport = None

    def __init__(self, listener=None, serializer=None):
        super().__init__(listener, serializer)

    def data_received(self, data):
        """Delegation from asyncio to JEP."""
        self._on_data_received(data)

    def connection_made(self, transport):
        """Delegation from asyncio to JEP."""
        self.transport = transport
        self._on_connection_made()

    def connection_lost(self, exc):
        """Delegation from asyncio to JEP."""
        self.transport = None
        self._on_connection_lost()

    @property
    def connected(self):
        return self.transport is not None

    def _send_data(self, data):
        if self.connected:
            self.transport.write(data)
