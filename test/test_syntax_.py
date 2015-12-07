import os
from unittest import mock
from jep.schema import SyntaxFormatType
from jep.syntax import SyntaxFileSet, SyntaxFile


def setup_function(function):
    # make sure all test function start from input folder:
    os.chdir(os.path.join(os.path.dirname(__file__), 'input'))


def test_syntax_file():
    s = SyntaxFile(mock.sentinel.NAME, mock.sentinel.PATH, mock.sentinel.FORMAT, ('ext1', 'ext2'))
    assert s.name == mock.sentinel.NAME
    assert s.path == mock.sentinel.PATH
    assert s.fileformat == mock.sentinel.FORMAT
    assert len(s.extensions) == 2
    assert 'ext1' in s.extensions
    assert 'ext2' in s.extensions


def test_syntax_file_definition():
    s = SyntaxFile('mcmake.tmLanguage', 'syntax/mcmake.tmLanguage', SyntaxFormatType.textmate, ('cmake',))
    d = s.definition
    assert 'string.quoted.double.mcmake' in d
    assert len(d) == 2837


def test_syntax_file_normalized_extension():
    assert SyntaxFile.normalized_extension(None) is None
    assert SyntaxFile.normalized_extension('.ext') == 'ext'
    assert SyntaxFile.normalized_extension('.Ext') == 'ext'
    assert SyntaxFile.normalized_extension('.EXT') == 'ext'
    assert SyntaxFile.normalized_extension('ext') == 'ext'
    assert SyntaxFile.normalized_extension('Ext') == 'ext'
    assert SyntaxFile.normalized_extension('EXT') == 'ext'


def test_syntax_file_set_empty():
    sfiles = SyntaxFileSet()
    assert not sfiles
    assert len(sfiles) == 0
    assert not sfiles.extension_map


def test_syntax_file_set_add():
    sfiles = SyntaxFileSet()
    sfiles.add(SyntaxFile(mock.sentinel.NAMEA, mock.sentinel.PATHA, mock.sentinel.FORMATA, ('extA1', 'extA2')))
    sfiles.add(SyntaxFile(mock.sentinel.NAMEB, mock.sentinel.PATHB, mock.sentinel.FORMATB, ('extB1', 'extB2')))

    assert len(sfiles) == 2
    s = SyntaxFile(mock.sentinel.NAMEB, mock.sentinel.PATHB, mock.sentinel.FORMATB, ('extB1', 'extB2'))
    assert s in sfiles

    assert sfiles.extension_map['exta1'].path == mock.sentinel.PATHA
    assert sfiles.extension_map['exta2'].path == mock.sentinel.PATHA
    assert sfiles.extension_map['extb1'].path == mock.sentinel.PATHB
    assert sfiles.extension_map['extb2'].path == mock.sentinel.PATHB


def test_syntax_file_set_add_syntax_file():
    sfiles = SyntaxFileSet()
    sfiles.add_syntax_file(mock.sentinel.NAME1, mock.sentinel.PATHA, mock.sentinel.FORMATA, ('extA1', 'extA2'))
    assert len(sfiles) == 1
    s = SyntaxFile(mock.sentinel.NAME1, mock.sentinel.PATHA, mock.sentinel.FORMATA, ('extA1', 'extA2'))
    assert s in sfiles


def test_syntax_file_set_remove():
    sfiles = SyntaxFileSet()
    sfiles.add(SyntaxFile(mock.sentinel.NAMEA, mock.sentinel.PATHA, mock.sentinel.FORMATA, ('extA1', 'extA2')))
    sfiles.add(SyntaxFile(mock.sentinel.NAMEB, mock.sentinel.PATHB, mock.sentinel.FORMATB, ('extB1', 'extB2')))
    sfiles.remove(SyntaxFile(mock.sentinel.NAMEB, mock.sentinel.PATHB, mock.sentinel.FORMATB, ('extB1', 'extB2')))

    assert len(sfiles) == 1
    assert SyntaxFile(mock.sentinel.NAMEA, mock.sentinel.PATHA, mock.sentinel.FORMATA, ('extA1', 'extA2')) in sfiles

    assert len(sfiles.extension_map) == 2
    assert sfiles.extension_map['exta1'].path == mock.sentinel.PATHA
    assert sfiles.extension_map['exta2'].path == mock.sentinel.PATHA


def test_syntax_file_set_filtered():
    s = SyntaxFileSet()

    s1 = SyntaxFile(mock.sentinel.NAME1, mock.sentinel.PATH1, mock.sentinel.FORMATA, ['ext1a', 'ext1b'])
    s2 = SyntaxFile(mock.sentinel.NAME2, mock.sentinel.PATH2, mock.sentinel.FORMATA, ['ext2a', 'ext2b'])

    s.add(s1)
    s.add(s2)
    s.add(SyntaxFile(mock.sentinel.NAME3, mock.sentinel.PATH3, mock.sentinel.FORMATB, ['ext3a', 'ext3b']))

    assert not list(s.filtered(mock.sentinel.FORMATC, ['ext1a', 'ext2a', 'ext3a']))
    assert not list(s.filtered(mock.sentinel.FORMATA, ['ext4', 'ext3a', 'ext3b']))

    f = list(s.filtered(mock.sentinel.FORMATA, ['ext4', 'ext1a', 'ext2b']))
    assert len(f) == 2
    assert s1 in f
    assert s2 in f
