from setuptools import setup, find_packages

# TODO Provide test configuration.
# TODO Integrate test runner for py.test.
# TODO Limit to Python 3.3+.
# TODO For Python 3.3, install enum dependency.

setup(
    name='jep',
    version='0.5.0',
    packages=find_packages(),
    url='https://github.com/jep-project/jep-python',
    license='',
    author='Mike Pagel',
    author_email='mike@mpagel.de',
    description='Python implementation of the Joint Editors Protocol, see http://joint-editors.org/.'
)
