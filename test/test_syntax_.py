import os
from unittest import mock

from jep.schema import SyntaxFormatType
from jep.syntax import SyntaxFileSet, SyntaxFile, normalized_extension


def setup_function(function):
    # make sure all test function start from input folder:
    os.chdir(os.path.join(os.path.dirname(__file__), 'input'))


def test_syntax_file():
    s = SyntaxFile(mock.sentinel.PATH, mock.sentinel.FORMAT, (mock.sentinel.EXT1, mock.sentinel.EXT2))
    assert s.path == mock.sentinel.PATH
    assert s.format_ == mock.sentinel.FORMAT
    assert len(s.extensions) == 2
    assert mock.sentinel.EXT1 in s.extensions
    assert mock.sentinel.EXT2 in s.extensions


def test_syntax_file_definition():
    s = SyntaxFile('syntax/mcmake.tmLanguage', SyntaxFormatType.textmate, ('cmake',))
    d = s.definition
    assert 'string.quoted.double.mcmake' in d
    assert len(d) == 2837


def test_normalized_extension():
    assert normalized_extension(None) is None
    assert normalized_extension('.ext') == 'ext'
    assert normalized_extension('.Ext') == 'ext'
    assert normalized_extension('.EXT') == 'ext'
    assert normalized_extension('ext') == 'ext'
    assert normalized_extension('Ext') == 'ext'
    assert normalized_extension('EXT') == 'ext'


def test_syntax_file_set_empty():
    sfiles = SyntaxFileSet()
    assert not sfiles
    assert len(sfiles) == 0
    assert not sfiles.extension_map


def test_syntax_file_set_add():
    sfiles = SyntaxFileSet()
    sfiles.add(SyntaxFile(mock.sentinel.PATHA, mock.sentinel.FORMATA, (mock.sentinel.EXTA1, mock.sentinel.EXTA2)))
    sfiles.add(SyntaxFile(mock.sentinel.PATHB, mock.sentinel.FORMATB, (mock.sentinel.EXTB1, mock.sentinel.EXTB2)))

    assert len(sfiles) == 2
    s = SyntaxFile(mock.sentinel.PATHB, mock.sentinel.FORMATB, (mock.sentinel.EXTB1, mock.sentinel.EXTB2))
    assert s in sfiles

    assert sfiles.extension_map[mock.sentinel.EXTA1].path == mock.sentinel.PATHA
    assert sfiles.extension_map[mock.sentinel.EXTA2].path == mock.sentinel.PATHA
    assert sfiles.extension_map[mock.sentinel.EXTB1].path == mock.sentinel.PATHB
    assert sfiles.extension_map[mock.sentinel.EXTB2].path == mock.sentinel.PATHB


def test_syntax_file_set_remove():
    sfiles = SyntaxFileSet()
    sfiles.add(SyntaxFile(mock.sentinel.PATHA, mock.sentinel.FORMATA, (mock.sentinel.EXTA1, mock.sentinel.EXTA2)))
    sfiles.add(SyntaxFile(mock.sentinel.PATHB, mock.sentinel.FORMATB, (mock.sentinel.EXTB1, mock.sentinel.EXTB2)))
    sfiles.remove(SyntaxFile(mock.sentinel.PATHB, mock.sentinel.FORMATB, (mock.sentinel.EXTB1, mock.sentinel.EXTB2)))

    assert len(sfiles) == 1
    assert SyntaxFile(mock.sentinel.PATHA, mock.sentinel.FORMATA, (mock.sentinel.EXTA1, mock.sentinel.EXTA2)) in sfiles

    assert len(sfiles.extension_map) == 2
    assert sfiles.extension_map[mock.sentinel.EXTA1].path == mock.sentinel.PATHA
    assert sfiles.extension_map[mock.sentinel.EXTA2].path == mock.sentinel.PATHA
