"""Management of code and DSL syntax definitions."""
import collections


class SyntaxFile:
    """Container for reference to syntax file and the extensions it supports."""

    def __init__(self, path, format_, extensions):
        self.path = path
        self.format_ = format_
        self.extensions = extensions
        self._definition = None

    def __eq__(self, other):
        return self.path == other.path and self.format_ == other.format_ and self.extensions == other.extensions

    def __hash__(self):
        return hash(self.path)

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

    def discard(self, value):
        if value in self.data:
            self.data.discard(value)
            for extension in value.extensions:
                self.extension_map.pop(extension)


def normalized_extension(extension):
    """Returns extension in normalized form, i.e. without leading dot and all lower capitals."""
    if not extension:
        return None
    if extension.startswith('.'):
        return extension[1:].lower()
    else:
        return extension.lower()
