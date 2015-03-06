import re
from os.path import split, splitext, abspath, exists


def find_service_config(file):
    last_dir = None
    dir = abspath(_dirname(file))
    search_pattern = _file_pattern(file)
    while dir != last_dir:
        config_file = dir + '/.jep'
        if exists(config_file):
            configs = _parse_config_file(config_file)
            for config in configs:
                if search_pattern in config.patterns:
                    return config
        last_dir = dir
        dir = _dirname(dir)
    return None


class ServiceConfig(object):
    def __init__(self, file, patterns, command):
        self.file = file
        self.patterns = patterns
        self.command = command


def _file_pattern(file):
    base, ext = splitext(file)
    if len(ext) > 0:
        return '*' + ext
    else:
        return split(file)[1]


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


# returns input if input is file system root
def _dirname(file):
    return split(file)[0]

