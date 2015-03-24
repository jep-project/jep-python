"""JEP service configuration."""
import hashlib
import re
from os.path import splitext, abspath, exists, dirname, join, basename


class ServiceConfig:
    """Represents configuration of a single JEP service."""

    def __init__(self, config_file_path, patterns, command, checksum):
        self.config_file_path = config_file_path
        self.patterns = tuple(patterns)
        self.command = command
        self.checksum = checksum

    @property
    def selector(self):
        """Key used during selection of the backend service to run for a certain file."""
        return hash((self.config_file_path, self.patterns))


class ServiceConfigProvider:
    """Loads JEP configuration files and provides a matching service configuration."""

    REPAT_SERVICE_SPEC = re.compile(r'^(?P<patterns>[^:]+)\s*:\s*^(?P<command>.*)$\s*', re.MULTILINE)
    REPAT_FILE_PATTERN = re.compile(r'[^,\s]+')

    @classmethod
    def provide_for(cls, edited_file_name, config_file_name='.jep'):
        """Returns service configuration for given file name that is going to be edited."""
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
            checksum = cls._checksum(content)

        for m in cls.REPAT_SERVICE_SPEC.finditer(content):
            patterns = cls.REPAT_FILE_PATTERN.findall(m.group('patterns'))
            if patterns:
                yield ServiceConfig(config_file_path, patterns, m.group('command'), checksum)

    @classmethod
    def checksum(cls, config_file_path):
        """Computes a checksum over content of given file."""
        with open(config_file_path) as config_file:
            content = config_file.read()
        return cls._checksum(content)

    @classmethod
    def _checksum(cls, string):
        """Computes a checksum over given string."""
        return hashlib.sha1(string.encode()).digest()

