"""Start script for JEP backend service."""
import logging
from jep.backend import Backend, FrontendListener
from test.logconfig import configure_test_logger

configure_test_logger()

_logger = logging.getLogger('jep.backend.sample')


class Listener(FrontendListener):
    def on_shutdown(self, context):
        _logger.info('Received shutdown in listener.')


Backend([Listener()]).start()
