from jep.frontend import Frontend, State


def test_provide_connection_unhandled_file():
    frontend = Frontend()
    assert not frontend.provide_connection('some.unknown')

