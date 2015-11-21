"""Management of code and DSL syntax definitions."""
import collections

SyntaxFile = collections.namedtuple('SyntaxFile', ['path', 'format', 'extensions'])
SyntaxFile.__doc__ = "Container for reference to syntax file and the extensions it supports."


class SyntaxFiles(collections.MutableSet):
    """Collection of SyntaxFiles, with additional lookup of syntax by extension."""

    def __init__(self):
        self.data = set()
        #: Cache for syntax lookup by extension.
        self.by_extension = dict()

    def __contains__(self, x):
        return x in self.data

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def add(self, value):
        self.data.add(value)
        for extension in value.extensions:
            self.by_extension[extension] = value

    def discard(self, value):
        if value in self.data:
            self.data.discard(value)
            for extension in value.extensions:
                self.by_extension.pop(extension)
