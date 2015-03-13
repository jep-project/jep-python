"""JEP message types."""
from enum import Enum
from jep.serializer import Serializable


def class_by_msgname(name):
    """Returns message class by name in message protocol."""
    # for now class names and message name is identical, later we can restrict or map here as well:
    return locals()[name]


class Shutdown(Serializable):
    pass


class BackendAlive:
    pass


class ContentSync:
    def __init__(self, file: str, data: bytes, start: int=0, end: int=-1):
        self.file = file
        self.start = start
        self.end = end
        self.data = data


class OutOfSync:
    def __init__(self, file: str):
        self.file = file


class Severity(Enum):
    Debug = 1
    Info = 2
    Warn = 3
    Error = 4
    Fatal = 5


class Problem:
    def __init__(self, message: str, severity: Severity, line: int):
        self.message = message
        self.severity = severity
        self.line = line


class FileProblems:
    def __init__(self, file: str, problems: [Problem], total: int=None, start: int=0, end: int=None):
        self.file = file
        self.problems = problems
        self.total = total
        self.start = start
        self.end = end


class ProblemUpdate:
    def __init__(self, file_problems: [FileProblems], partial: bool=False):
        self.file_problems = file_problems
        self.partial = partial


class CompletionRequest:
    def __init__(self, token: str, file: str, pos: int, limit: int=None):
        self.token = token
        self.file = file
        self.pos = pos
        self.limit = limit


class SemanticType(Enum):
    Comment = 1
    Type = 2
    String = 3
    Number = 4
    Identifier = 5
    Keyword = 6
    Label = 7
    Link = 8
    Special1 = 9
    Special2 = 10
    Special3 = 11
    Special4 = 12
    Special5 = 13


class CompletionOption:
    def __init__(self, display: str, desc: str=None, semantics: SemanticType=None, extension_id: str=None):
        self.display = display
        self.desc = desc
        self.semantics = semantics
        self.extension_id = extension_id


class CompletionResponse:
    def __init__(self, token: str, start: int, end: int, limit_exceeded: bool, options: [CompletionOption]=None):
        self.token = token
        self.start = start
        self.end = end
        self.limit_exceeded = limit_exceeded
        self.options = options
