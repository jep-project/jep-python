import sys
from setuptools.command.test import test as TestCommand


def main():
    """Wrapper around imports to prevent them being executed immediately upon this module being only imported (Sublime plugin workaround)."""
    from setuptools import setup, find_packages

    # TODO Limit to Python 3.3+.
    # TODO For Python 3.3, install enum dependency.

    class PyTestCommand(TestCommand):
        user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

        def initialize_options(self):
            TestCommand.initialize_options(self)
            self.pytest_args = []

        def finalize_options(self):
            TestCommand.finalize_options(self)
            self.test_args = []
            self.test_suite = True

        def run_tests(self):
            #import here, cause outside the eggs aren't loaded
            import pytest

            errno = pytest.main(self.pytest_args)
            sys.exit(errno)

    setup(
        name='jep',
        version='0.5.0',
        packages=find_packages(),
        install_requires=[
            'u-msgpack-python'
        ],
        tests_require=[
            'pytest'
        ],
        cmdclass={'test': PyTestCommand},
        url='https://github.com/jep-project/jep-python',
        license='',
        author='Mike Pagel',
        author_email='mike@mpagel.de',
        description='Python implementation of the Joint Editors Protocol, see http://joint-editors.org/.'
    )


if __name__ == '__main__':
    main()