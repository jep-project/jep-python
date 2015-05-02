"""Test of content synchronization of KEP backend."""
from unittest import mock
from jep.content import ContentMonitor, SynchronizationResult


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
