from unittest import mock

from jep.syntax import SyntaxFiles, SyntaxFile


def test_syntax_file():
    s = SyntaxFile(mock.sentinel.PATH, mock.sentinel.FORMAT, (mock.sentinel.EXT1, mock.sentinel.EXT2))
    assert s.path == mock.sentinel.PATH
    assert s.format == mock.sentinel.FORMAT
    assert len(s.extensions) == 2
    assert mock.sentinel.EXT1 in s.extensions
    assert mock.sentinel.EXT2 in s.extensions


def test_syntax_files_empty():
    sfiles = SyntaxFiles()
    assert not sfiles
    assert len(sfiles) == 0
    assert not sfiles.by_extension


def test_syntax_files_add():
    sfiles = SyntaxFiles()
    sfiles.add(SyntaxFile(mock.sentinel.PATHA, mock.sentinel.FORMATA, (mock.sentinel.EXTA1, mock.sentinel.EXTA2)))
    sfiles.add(SyntaxFile(mock.sentinel.PATHB, mock.sentinel.FORMATB, (mock.sentinel.EXTB1, mock.sentinel.EXTB2)))

    assert len(sfiles) == 2
    s = SyntaxFile(mock.sentinel.PATHB, mock.sentinel.FORMATB, (mock.sentinel.EXTB1, mock.sentinel.EXTB2))
    assert s in sfiles

    assert sfiles.by_extension[mock.sentinel.EXTA1].path == mock.sentinel.PATHA
    assert sfiles.by_extension[mock.sentinel.EXTA2].path == mock.sentinel.PATHA
    assert sfiles.by_extension[mock.sentinel.EXTB1].path == mock.sentinel.PATHB
    assert sfiles.by_extension[mock.sentinel.EXTB2].path == mock.sentinel.PATHB


def test_syntax_files_remove():
    sfiles = SyntaxFiles()
    sfiles.add(SyntaxFile(mock.sentinel.PATHA, mock.sentinel.FORMATA, (mock.sentinel.EXTA1, mock.sentinel.EXTA2)))
    sfiles.add(SyntaxFile(mock.sentinel.PATHB, mock.sentinel.FORMATB, (mock.sentinel.EXTB1, mock.sentinel.EXTB2)))
    sfiles.remove(SyntaxFile(mock.sentinel.PATHB, mock.sentinel.FORMATB, (mock.sentinel.EXTB1, mock.sentinel.EXTB2)))

    assert len(sfiles) == 1
    assert SyntaxFile(mock.sentinel.PATHA, mock.sentinel.FORMATA, (mock.sentinel.EXTA1, mock.sentinel.EXTA2)) in sfiles

    assert len(sfiles.by_extension) == 2
    assert sfiles.by_extension[mock.sentinel.EXTA1].path == mock.sentinel.PATHA
    assert sfiles.by_extension[mock.sentinel.EXTA2].path == mock.sentinel.PATHA
