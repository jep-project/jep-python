"""Management of syntax highlighting support by backend."""
import os


class StaticSyntaxProvider:
    """Keeps track of static syntax definitions held in backend and provides them to frontend.

    Class may be used by frontend and backend implementations to store the syntax definitions provided by specific backend application to backend class and by frontend
    class to frontend plugins."""

    def __init__(self):
        self.extension_to_syntax_filepath_map = {}

    def register(self, syntax_filepath, *extensions):
        """Adds a new syntax definition file for the given file extensions."""
        assert syntax_filepath is not None, 'No syntax file specified.'
        assert os.path.exists(syntax_filepath), 'Syntax file not found: %s' % syntax_filepath
        assert extensions, 'Extensions must be assiciated with syntax file %s.' % syntax_filepath

        for extension in extensions:
            self.extension_to_syntax_filepath_map[extension.lower()] = syntax_filepath

    def get_syntaxes(self, *extensions):
        """Returns a dictionary of syntax files by extension."""

        if not extensions:
            # return full list of no selection is made:
            return self.extension_to_syntax_filepath_map
        else:
            # return filtered map:
            syntax_filepath_map = {}

            for extension in (e.lower() for e in extensions):
                filepath = self.extension_to_syntax_filepath_map.get(extension)
                if filepath:
                    syntax_filepath_map[extension] = filepath

            return syntax_filepath_map
