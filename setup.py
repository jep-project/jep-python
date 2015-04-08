"""Setup script for jep.python."""


def main():
    """Wrapper around imports to prevent them being executed immediately upon this module being only imported (Sublime plugin workaround)."""
    from setuptools import setup, find_packages
    from setuptools.command.test import test as TestCommand
    import sys

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

    # configure dependencies corresponding to interpreter version:
    install_requires = ['u-msgpack-python']

    if sys.version_info < (3, 3):
        print('This Python version is not supported, minimal version 3.3 is required.')
        sys.exit(1)
    if sys.version_info < (3, 4):
        install_requires.append('enum34')

    setup(
        name='jep',
        version='0.5.0',
        packages=find_packages(),
        install_requires=install_requires,
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