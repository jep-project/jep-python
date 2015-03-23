"""Interfaces that may be used to listen to frontend and backend events.

The classes in this module do not implement any logic and their use is
optional. Since they do not raise non-implemented methods, they help
selective implementations of callbacks.
"""


class FrontendMessageListener:
    """API to listen to messages from frontend."""

    def on_shutdown(self, context):
        return NotImplemented

    def on_content_sync(self, content_sync, context):
        return NotImplemented

    def on_completion_request(self, completion_request, context):
        return NotImplemented


class BackendMessageListener:
    """API to listen to messages from backend."""

    def on_backend_alive(self, context):
        return NotImplemented

    def on_out_of_sync(self, out_of_sync, context):
        return NotImplemented

    def on_problem_update(self, problem_update, context):
        return NotImplemented

    def on_completion_response(self, completion_response, context):
        return NotImplemented
