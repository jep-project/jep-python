# jep-python [![Build Status](https://travis-ci.org/jep-project/jep-python.svg?branch=master)](https://travis-ci.org/jep-project/jep-python)
This is the Python implementation of the JEP protocol, providing language authors with a frontend library for IDE/editor
integration and a backend library for language support.

This implementation is currently compatible with Python 3.3+.

## Backend support

Implementing JEP based support for a custom language is easy. Simply derive one or listener classes to respond to frontend
events and then run the backend with those listeners.

'''python
from jep.backend import Backend, FrontendListener

class Listener(FrontendListener):
    def on_shutdown(self, context):
        _logger.info('Received shutdown in listener.')
'''
