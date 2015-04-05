import logging
import datetime
from jep.frontend import Frontend, BackendListener, State
from test.logconfig import configure_test_logger

_logger = logging.getLogger('jep.frontend.sample')


class MyListener(BackendListener):
    def on_backend_alive(self, context):
        context.disconnect()


def test_frontend_starts_stops_backend():
    configure_test_logger()
    frontend = Frontend([MyListener()])
    connection = frontend.get_connection('../scripts/localfile.mydsl')

    started = datetime.datetime.now()
    cycles = 0
    while connection.state is not State.Disconnected:
        connection.run(datetime.timedelta(seconds=0.1))
        cycles += 1
    ended = datetime.datetime.now()

    _logger.info('Frontend executed %d cycles in %.2f seconds.' % (cycles, (ended - started).total_seconds()))


if __name__ == '__main__':
    test_frontend_starts_stops_backend()