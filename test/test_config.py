import os
from jep.config import ServiceConfigProvider, ServiceConfig


def setup_function(function):
    # make sure all test function start from input folder:
    os.chdir(os.path.join(os.path.dirname(__file__), 'input'))


def test_service_config_provider():
    provider = ServiceConfigProvider()
    sc = provider.provide_for('test/test.rb')
    assert sc.command == 'ruby-command'
    assert os.path.exists(sc.config_file_path)
    assert sc.checksum

    sc = provider.provide_for('test/test.ruby')
    assert sc.command == 'ruby-command'
    assert os.path.exists(sc.config_file_path)

    sc = provider.provide_for('test/test.ruby2')
    assert sc.command == 'ruby-command'
    assert os.path.exists(sc.config_file_path)

    sc = provider.provide_for('other-folder/test.c')
    assert sc.command == 'c-command'
    assert os.path.exists(sc.config_file_path)

    sc = provider.provide_for('other-folder/fullname')
    assert sc.command == 'fullname-command'


def test_service_config_provider_failed_extension():
    provider = ServiceConfigProvider()
    sc = provider.provide_for('test/test.unknown')
    assert sc is None


def test_service_config_provider_failed_config_file():
    os.chdir('..')
    provider = ServiceConfigProvider()
    sc = provider.provide_for('test/test.rb')
    assert sc is None


def test_service_config_provider_from_subfolders():
    os.chdir('sub1')
    provider = ServiceConfigProvider()
    assert provider.provide_for('test/test.rb')
    os.chdir('sub2')
    assert provider.provide_for('test/test.rb')


def test_service_config_selector():
    sc1 = ServiceConfig('path1', ['*.txt'], 'doit.exe', '1234')
    sc2 = ServiceConfig('path1', ['*.txt'], 'doit.exe', '1234')
    sc3 = ServiceConfig('path2', ['*.txt'], 'doit.exe', '1234')
    sc4 = ServiceConfig('path1', ['*.doc'], 'doit.exe', '1234')

    assert sc1.selector == sc2.selector
    assert not sc1.selector == sc3.selector
    assert not sc2.selector == sc4.selector


def test_service_config_provider_checksum():
    provider = ServiceConfigProvider()
    sc = provider.provide_for('test/test.rb')
    assert sc.checksum
    assert provider.checksum('.jep') == sc.checksum
    assert not provider.checksum('other-jep') == sc.checksum
    assert provider.checksum('not-existing-file') is None
