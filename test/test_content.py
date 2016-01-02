"""Test of content synchronization of KEP backend."""
from unittest import mock
from jep.content import ContentMonitor, SynchronizationResult, NewlineMode


def test_content_empty():
    monitor = ContentMonitor()
    assert monitor[mock.sentinel.UNKNOWN_FILE] is None


def test_initial_sync():
    monitor = ContentMonitor()
    assert monitor.synchronize(mock.sentinel.FILEPATH, 'This is the string.', 0) == SynchronizationResult.Updated
    assert monitor[mock.sentinel.FILEPATH] == 'This is the string.'


def test_replace_all():
    monitor = ContentMonitor()
    monitor.synchronize(mock.sentinel.FILEPATH, 'This is the string.', 0)
    assert monitor.synchronize(mock.sentinel.FILEPATH, 'Something else', 0) == SynchronizationResult.Updated
    assert monitor[mock.sentinel.FILEPATH] == 'Something else'


def test_replace_part():
    monitor = ContentMonitor()
    monitor.synchronize(mock.sentinel.FILEPATH, 'This is the string.', 0)
    assert monitor.synchronize(mock.sentinel.FILEPATH, 'WAS', 5, 7) == SynchronizationResult.Updated
    assert monitor[mock.sentinel.FILEPATH] == 'This WAS the string.'


def test_insert_beginning():
    monitor = ContentMonitor()
    monitor.synchronize(mock.sentinel.FILEPATH, 'This is the string.', 0)
    assert monitor.synchronize(mock.sentinel.FILEPATH, 'Listen: ', 0, 0) == SynchronizationResult.Updated
    assert monitor[mock.sentinel.FILEPATH] == 'Listen: This is the string.'


def test_append():
    monitor = ContentMonitor()
    monitor.synchronize(mock.sentinel.FILEPATH, 'This is the string.', 0)
    assert monitor.synchronize(mock.sentinel.FILEPATH, ' Really!', 19, 19) == SynchronizationResult.Updated
    assert monitor[mock.sentinel.FILEPATH] == 'This is the string. Really!'


def test_out_of_sync():
    monitor = ContentMonitor()
    monitor.synchronize(mock.sentinel.FILEPATH, 'This is the string.', 0)
    assert monitor.synchronize(mock.sentinel.FILEPATH, ' Really!', 20, 22) == SynchronizationResult.OutOfSync
    assert monitor[mock.sentinel.FILEPATH] == 'This is the string.'
    assert monitor.synchronize(mock.sentinel.FILEPATH, ' Really!', 10, 9) == SynchronizationResult.OutOfSync
    assert monitor[mock.sentinel.FILEPATH] == 'This is the string.'
    assert monitor.synchronize(mock.sentinel.FILEPATH, ' Really!', -1, 5) == SynchronizationResult.OutOfSync
    assert monitor[mock.sentinel.FILEPATH] == 'This is the string.'
    assert monitor.synchronize(mock.sentinel.FILEPATH, ' Really!', 0, -1) == SynchronizationResult.OutOfSync
    assert monitor[mock.sentinel.FILEPATH] == 'This is the string.'


def test_newline_mode_detect():
    assert NewlineMode.detect(None) == NewlineMode.Unknown
    assert NewlineMode.detect('') == NewlineMode.Unknown
    assert NewlineMode.detect('Hello') == NewlineMode.Unknown
    assert NewlineMode.detect('Hello\n') == NewlineMode.N
    assert NewlineMode.detect('\nHello') == NewlineMode.N
    assert NewlineMode.detect('He\nllo') == NewlineMode.N
    assert NewlineMode.detect('He\nllo\n') == NewlineMode.N
    assert NewlineMode.detect('He\nllo\n ') == NewlineMode.N
    assert NewlineMode.detect('Hello\r') == NewlineMode.R
    assert NewlineMode.detect('Hello\r\n') == NewlineMode.RN
    assert NewlineMode.detect('\rHello\n') == NewlineMode.R | NewlineMode.N
    assert NewlineMode.detect('\r\nHello\n') == NewlineMode.RN | NewlineMode.N
    assert NewlineMode.detect('\r\nHel\rlo\n') == NewlineMode.RN | NewlineMode.N | NewlineMode.R == NewlineMode.All


def test_newline_mode_open_mode():
    assert NewlineMode.open_newline_mode(NewlineMode.N) is None
    assert NewlineMode.open_newline_mode(NewlineMode.R) == '\r'
    assert NewlineMode.open_newline_mode(NewlineMode.RN) == '\r\n'
    assert NewlineMode.open_newline_mode(NewlineMode.All) == ''
