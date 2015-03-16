"""Framework independent PEP backend implementation."""
from enum import Enum, unique
from jep.protocol import JepProtocolListener

# range to search for available ports:
PORT_RANGE = (30000, 30100)

# Number of seconds between backend alive messages:
PERIOD_BACKEND_ALIVE_SEC = 1


@unique
class BackendState(Enum):
    Diconnected = 1
    Listening = 2
    Connected = 3
    ShutdownPending = 4


class Backend(JepProtocolListener):
    def __init__(self):
        self.state = BackendState.Diconnected
