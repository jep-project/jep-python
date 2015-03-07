import os
from jep.config import find_service_config


def setup_function(function):
    # make sure all test function start from input folder:
    os.chdir(os.path.join(os.path.dirname(__file__), 'input'))


def test_find_service_config():
    sc = find_service_config('test/test.rb')
    assert sc.command == 'ruby-command'
    assert os.path.exists(sc.config_file_path)

    sc = find_service_config('test/test.ruby')
    assert sc.command == 'ruby-command'
    assert os.path.exists(sc.config_file_path)

    sc = find_service_config('test/test.ruby2')
    assert sc.command == 'ruby-command'
    assert os.path.exists(sc.config_file_path)

    sc = find_service_config('other-folder/test.c')
    assert sc.command == 'c-command'
    assert os.path.exists(sc.config_file_path)

    sc = find_service_config('other-folder/fullname')
    assert sc.command == 'fullname-command'


def test_find_service_config_failed_extension():
    sc = find_service_config('test/test.unknown')
    assert sc is None


def test_find_service_config_failed_config_file():
    os.chdir('..')
    sc = find_service_config('test/test.rb')
    assert sc is None


def test_find_service_config_from_subfolders():
    os.chdir('sub1')
    assert find_service_config('test/test.rb')
    os.chdir('sub2')
    assert find_service_config('test/test.rb')
