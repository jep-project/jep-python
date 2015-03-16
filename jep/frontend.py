"""JEP frontend support."""


class Frontend:
    """Top level frontend class, once to be instantiated per editor plugin."""

    def connector_for_file(self, filename):
        pass


class BackendConnector:
    """Manager for a connection to a single backend service."""
    pass

