"""Management of code and DSL syntax definitions."""
import collections


class SyntaxFile:
    """Container for reference to syntax file and the extensions it supports."""

    def __init__(self, path, fileformat, extensions):
        self.path = path
        self.fileformat = fileformat
        self.extensions = [self.normalized_extension(e) for e in extensions]
        self._definition = None

    def __eq__(self, other):
        return self.path == other.path and self.fileformat == other.fileformat and self.extensions == other.extensions

    def __hash__(self):
        return hash(self.path)

    @classmethod
    def normalized_extension(cls, extension):
        """Returns extension in normalized form, i.e. without leading dot and all lower capitals."""
        if not extension:
            return None
        if extension.startswith('.'):
            return extension[1:].lower()
        else:
            return extension.lower()

    @property
    def definition(self):
        if not self._definition:
            with open(self.path) as syntaxfile:
                self._definition = syntaxfile.read()
        return self._definition


class SyntaxFileSet(collections.MutableSet):
    """Collection of SyntaxFiles, with additional lookup of syntax by extension."""

    def __init__(self):
        self.data = set()
        #: Cache for syntax lookup by extension.
        self.extension_map = dict()

    def __contains__(self, x):
        return x in self.data

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def add(self, value):
        self.data.add(value)
        for extension in value.extensions:
            self.extension_map[extension] = value

    def add_syntax_file(self, path, fileformat, extensions):
        self.add(SyntaxFile(path, fileformat, extensions))

    def discard(self, value):
        if value in self.data:
            self.data.discard(value)
            for extension in value.extensions:
                self.extension_map.pop(extension)

    def filtered(self, fileformat, extensions):
        """Returns a filtered (Python) set for the given extensions and in the specified file file format."""
        if extensions:
            syntax_files = {self.extension_map[ext] for ext in extensions if ext in self.extension_map}
        else:
            # return all known syntax definitions:
            syntax_files = self.data

        return set(filter(lambda s: s.fileformat is fileformat, syntax_files))
