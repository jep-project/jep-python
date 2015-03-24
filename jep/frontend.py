"""JEP frontend support."""
import collections
from jep.config import ServiceConfigProvider


class Frontend:
    """Top level frontend class, once to be instantiated per editor plugin."""

    def __init__(self, service_config_provider=ServiceConfigProvider()):
        self.service_config_provider = service_config_provider
        self.connection_by_service_selector = collections.defaultdict()

    def provide_connection(self, filename):
        """Returns connection to a backend service that can deal with the given file."""
        connection = None

        service_config = self.service_config_provider.provide_for(filename)
        if service_config:
            # check whether this service reference was used before:
            connection = self.connection_by_service_selector[service_config.selector]
            if connection:
                if not connection.service_config.checksum == self.service_config_provider.checksum(service_config.config_file_path):
                    # configuration changed:
                    connection.stop()
                    connection = None

            if not connection:
                connection = self._connect(service_config)
                self.connection_by_service_selector[service_config.selector] = connection

        return connection

    def _connect(self, service_config):
        return BackendConnection()


class BackendConnection:
    """Connection to a single backend service."""
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