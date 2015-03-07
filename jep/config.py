"""JEP service configuration."""
import re
from os.path import splitext, abspath, exists, dirname, join, basename


class ServiceConfig:
    """Represents configuration of a single JEP service."""

    def __init__(self, config_file_path, patterns, command):
        self.config_file_path = config_file_path
        self.patterns = patterns
        self.command = command


class ServiceConfigProvider:
    """Loads JEP configuration files and provides a matching service configuration."""

    @classmethod
    def provide_service_config(cls, edited_file_name, config_file_name='.jep'):
        lastdir = None
        curdir = dirname(abspath(edited_file_name))
        search_pattern = cls._file_pattern(edited_file_name)

        while curdir != lastdir:
            config_file_path = join(curdir, config_file_name)
            if exists(config_file_path):
                for config in cls._configurations(config_file_path):
                    if search_pattern in config.patterns:
                        return config
            lastdir = curdir
            curdir = dirname(curdir)

        # not found:
        return None

    @classmethod
    def _file_pattern(cls, file_name):
        """Determine file pattern to look for in config file, either *.ext or basename."""
        base, ext = splitext(file_name)
        if ext:
            return '*%s' % ext
        else:
            return basename(file_name)

    @classmethod
    def _configurations(cls, config_file_path):
        """Iterator over service configurations in config file."""

        with open(config_file_path) as config_file:
            # to ease parsing read whole file at once, assuming it won't consume huge amounts of memory:
            content = config_file.read()

        for m in re.finditer(r'^(?P<patterns>[^:]+)\s*:\s*^(?P<command>.*)$\s*', content, re.MULTILINE):
            patterns = re.findall(r'[^,\s]+', m.group('patterns'))
            if patterns:
                yield ServiceConfig(config_file_path, patterns, m.group('command'))


def find_service_config(filename):
    return ServiceConfigProvider.provide_service_config(filename)
