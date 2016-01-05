jep-python |Build Status|
=========================

This is the Python implementation of the JEP protocol, providing
language authors with a frontend library for IDE/editor integration and
a backend library for language support.

This implementation is currently compatible with Python 3.3+.

Backend support
---------------

Implementing JEP based support for a custom language is easy. Simply
derive one or more listener classes to respond to frontend messages and
then run the backend with those listeners.

.. code:: python

    from jep_py.backend import Backend, FrontendListener

    class Listener(FrontendListener):
        def on_completion_request(self, completion_request, context):
            # process completion request and send back response:
            completion_response = f(completion_request)
            context.send_message(completion_response)
            
    # instantiate and start backend service with our listeners:
    listener = Listener()
    backend = Backend([listener])
    backend.start()

Callbacks that are not needed by a certain listener do not need to be
overridden in the derived class.

While the user is editing a file in a connected IDE the frontend will
repeatedly send ``ContentSync`` objects to the backend. The backend
implementation already processes these messages internally and provides
an accumulated file view to client code. Since backend-internal message
processing is done *before* messages are passed to subscribed listeners,
you can process the latest view of a file directly inside your
listener's handler of ``ContentSync`` by accessing the context's
``content_monitor`` filepath dictionary:

.. code:: python

    def on_content_sync(self, content_sync, context):
        # get the content monitor's view of the file that was just updated:
        file_content = context.content_monitor[content_sync.file]
        
        # ...

Frontend support
----------------

Similarly in an IDE frontend you again derive listener classes, this
time listening to backend messages. Since the frontend initiates the
connection you additionally have to create such a connection for a
certain language. JEP service lookup is then used to determine the
supporting backend and the frontend will start it in its own subprocess.

Here is an example shutting down the backend service upon reception of
its first alive message:

.. code:: python

    import datetime
    from jep_py.frontend import Frontend, BackendListener, State
    from jep_py.schema import Shutdown

    class MyListener(BackendListener):
        def on_backend_alive(self, context):
            context.send_message(Shutdown())


    frontend = Frontend([MyListener()])
    connection = frontend.get_connection('localfile.mydsl')

    while connection.state is not State.Disconnected:
        connection.run(datetime.timedelta(seconds=0.1))

.. |Build Status| image:: https://travis-ci.org/jep-project/jep-python.svg?branch=master
   :target: https://travis-ci.org/jep-project/jep-python
