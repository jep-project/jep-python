"""Content tracking in response to ContentSync messages."""
import enum
import logging
import collections

_logger = logging.getLogger(__name__)


@enum.unique
class SynchronizationResult(enum.Enum):
    #: Synchronization failed because tracked content and update are out of sync.
    OutOfSync = 1
    #: File content was updated successfully.
    Updated = 2


class ContentMonitor:
    """Monitors the file contents based on synchronization requests from a frontend.

    Current implementation uses straight forward Python strings, which involves multiple copies on insert:

        * Copy to first slice
        * Copy to second slice
        * Copy of all slices and inserted text to destination string

    If this becomes too much of a performance hit, it may be optimized, e.g. in form of an extension in C or
    a data structure that directly represents string edit operations (btree, ...).
    """

    def __init__(self):
        #: File contents by path.
        self._content_by_path = {}

    def __getitem__(self, filepath):
        """Returns the bytes know for file with given path."""
        return self._content_by_path.get(filepath, None)

    def synchronize(self, filepath, data, start, end=None):
        """Synchronizes content of given file."""

        content = self._content_by_path.get(filepath, '')
        length = len(content)

        # end index is optional:
        end = end if end is not None else length

        if start < 0 or start > length or end < 0 or end > length or start > end:
            _logger.warning('Received content sync for %s, with current length %d. Start index %d or end index %d inconsistent.' % (filepath, length, start, end))
            return SynchronizationResult.OutOfSync

        if start < 0:
            start = 0
        if end < 0:
            end = 0

        _logger.debug('Updating file %s from index %d to %d with "%s".' % (filepath, start, end, data))

        before = content[0:start]
        after = content[end:]

        self._content_by_path[filepath] = ''.join([before, data, after])
        return SynchronizationResult.Updated
