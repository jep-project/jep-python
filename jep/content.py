"""Content tracking in response to ContentSync messages."""
import enum
import io
import logging
import collections

_logger = logging.getLogger(__name__)


@enum.unique
class SynchronizationResult(enum.Enum):
    #: Synchronization failed because tracked content and update are out of sync.
    OutOfSync = 1
    #: No change to data after synchronization.
    Unchanged = 2
    #: File content changed.
    Modified = 3


class ContentMonitor:
    def __init__(self):
        #: File contents by path.
        self.bytes_by_path = collections.defaultdict(bytearray)

    def synchronize(self, filepath, start, end, data):
        """Synchronizes content of given file."""

        filebytes = self.bytes_by_path[filepath]
        length = len(filebytes)

        if start > length:
            _logger.warning('Received content sync for %s starting at index %d but known content length is only %d.' % (filepath, start, length))
            return SynchronizationResult.OutOfSync

        end = end if end is not None else length

        if start < 0:
            start = 0
        if end < 0:
            end = 0

        _logger.debug('Updating file %s from index %d to %d: %s' % (filepath, start, end, data))
        filepath[start:end] = data
