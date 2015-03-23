"""JEP frontend support."""


class Frontend:
    """Top level frontend class, once to be instantiated per editor plugin."""

    def connector_for_file(self, filename):
        pass


class BackendConnector:
    """Manager for a connection to a single backend service."""
    pass


class BackendListener:
    """API to listen to messages from backend, communicated by frontend."""

    def on_backend_alive(self, context):
        return NotImplemented

    def on_out_of_sync(self, out_of_sync, context):
        return NotImplemented

    def on_content_sync(self, content_sync, context):
        return NotImplemented

    def on_problem_update(self, problem_update, context):
        return NotImplemented

    def on_completion_response(self, completion_response, context):
        return NotImplemented