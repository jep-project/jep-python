import re
from os.path import split, splitext, abspath, exists, dirname, join, basename


CONFIG_FILE_NAME = '.jep'


def find_service_config(filename):
    lastdir = None
    curdir = abspath(dirname(filename))
    search_pattern = _file_pattern(filename)

    while curdir != lastdir:
        config_file = join(curdir, CONFIG_FILE_NAME)
        if exists(config_file):
            configs = _parse_config_file(config_file)
            for config in configs:
                if search_pattern in config.patterns:
                    return config
        lastdir = curdir
        curdir = dirname(curdir)

    # not found:
    return None


class ServiceConfig(object):
    def __init__(self, file, patterns, command):
        self.file = file
        self.patterns = patterns
        self.command = command


def _file_pattern(file):
    base, ext = splitext(file)
    if ext:
        return '*%s' % ext
    else:
        return basename(file)


def _parse_config_file(file):
    pattern_line_re = re.compile('^(.+):\s*$')
    has_non_space_re = re.compile('\S')
    colon_at_end_re = re.compile(':\s*$')
    configs = []
    with open(file) as f:
        lines = f.readlines()
        l = _shift(lines)
        while l:
            match = pattern_line_re.match(l)
            if match:
                patterns = []
                for p in match.group(1).split(','):
                    patterns.append(p.strip())
                l = _shift(lines)
                if l and has_non_space_re.match(l) and not colon_at_end_re.match(l):
                    configs.append(ServiceConfig(file, patterns, l.strip()))
                    l = _shift(lines)
            else:
                l = _shift(lines)
    return configs


def _shift(lst):
    if len(lst) > 0:
        return lst.pop(0)
    else:
        return None


