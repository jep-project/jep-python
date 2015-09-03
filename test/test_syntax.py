from unittest import mock
from jep.syntax import StaticSyntaxProvider


def test_empty_registry():
    provider = StaticSyntaxProvider()
    assert len(provider.get_syntaxes()) == 0
    assert len(provider.get_syntaxes('ext1')) == 0
    assert len(provider.get_syntaxes('ext1', 'ext2')) == 0


def test_get_all():
    provider = StaticSyntaxProvider()
    provider.register(mock.sentinel.SYNTAX_FILE, 'ext')
    provider.register(mock.sentinel.SYNTAX_FILE_2, 'ext2')
    syntaxes = provider.get_syntaxes()
    assert len(syntaxes) == 2
    assert syntaxes['ext'] == mock.sentinel.SYNTAX_FILE
    assert syntaxes['ext2'] == mock.sentinel.SYNTAX_FILE_2


def test_get_different():
    provider = StaticSyntaxProvider()
    provider.register(mock.sentinel.SYNTAX_FILE, 'ext')
    provider.register(mock.sentinel.SYNTAX_FILE_2, 'ext2')
    assert provider.get_syntaxes('ext')['ext'] == mock.sentinel.SYNTAX_FILE
    assert 'ext2' not in provider.get_syntaxes('ext')
    assert provider.get_syntaxes('ext2')['ext2'] == mock.sentinel.SYNTAX_FILE_2


def test_capitalization():
    provider = StaticSyntaxProvider()
    provider.register(mock.sentinel.SYNTAX_FILE, 'eXT')
    assert provider.get_syntaxes('ext')['ext'] == mock.sentinel.SYNTAX_FILE
    assert provider.get_syntaxes('EXT')['ext'] == mock.sentinel.SYNTAX_FILE
    assert provider.get_syntaxes('eXt')['ext'] == mock.sentinel.SYNTAX_FILE

    provider.register(mock.sentinel.SYNTAX_FILE_1, 'ext')
    assert provider.get_syntaxes('ext')['ext'] == mock.sentinel.SYNTAX_FILE_1
    assert provider.get_syntaxes('EXT')['ext'] == mock.sentinel.SYNTAX_FILE_1
    assert provider.get_syntaxes('eXt')['ext'] == mock.sentinel.SYNTAX_FILE_1
