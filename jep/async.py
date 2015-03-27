"""Asynchronous reader from file like object, used to read subprocess output without blocking.

This feature is not part of the Python 3.3 standard library. It was requested in PEP 3145 (Asynchronous I/O For subprocess.Popen) but
was deferred and is now available integrated into the standard library's asyncio module (Python 3.4+).

This implementation inspired by http://stefaanlippens.net/python-asynchronous-subprocess-pipe-reading.
"""
import queue
import threading


class AsynchronousFileReader(threading.Thread):
    """Helper class to implement asynchronous reading of a file in a separate thread.

    Pushes read lines on a queue to be consumed in another thread.
    """

    def __init__(self, file_, queue_=queue.Queue()):
        super().__init__()
        self.file_ = file_
        self.queue_ = queue_

    def run(self):
        """The body of the tread: read lines and put them on the queue."""
        for line in iter(self.file_.readline, ''):
            self.queue_.put(line)

    def eof(self):
        """Check whether there is no more content to expect."""
        return (not self.is_alive()) and self.queue_.empty()
