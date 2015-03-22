"""JEP message types."""
try:
    import enum
except ImportError:
    import jep.contrib.enum as enum

from jep.serializer import Serializable


class Shutdown(Serializable):
    pass


class BackendAlive(Serializable):
    pass


class ContentSync(Serializable):
    def __init__(self, file: str, data: bytes, start: int=0, end: int=-1):
        super().__init__()
        self.file = file
        self.start = start
        self.end = end
        self.data = data


class OutOfSync(Serializable):
    def __init__(self, file: str):
        super().__init__()
        self.file = file


@enum.unique
class Severity(enum.Enum):
    Debug = 1
    Info = 2
    Warn = 3
    Error = 4
    Fatal = 5


class Problem(Serializable):
    def __init__(self, message: str, severity: Severity, line: int):
        super().__init__()
        self.message = message
        self.severity = severity
        self.line = line


class FileProblems(Serializable):
    def __init__(self, file: str, problems: [Problem], total: int=None, start: int=0, end: int=None):
        super().__init__()
        self.file = file
        self.problems = problems
        self.total = total
        self.start = start
        self.end = end


class ProblemUpdate(Serializable):
    def __init__(self, file_problems: [FileProblems], partial: bool=False):
        super().__init__()
        self.file_problems = file_problems
        self.partial = partial


class CompletionRequest(Serializable):
    def __init__(self, token: str, file: str, pos: int, limit: int=None):
        super().__init__()
        self.token = token
        self.file = file
        self.pos = pos
        self.limit = limit


@enum.unique
class SemanticType(enum.Enum):
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


class CompletionOption(Serializable):
    def __init__(self, display: str, desc: str=None, semantics: SemanticType=None, extension_id: str=None):
        super().__init__()
        self.display = display
        self.desc = desc
        self.semantics = semantics
        self.extension_id = extension_id


class CompletionResponse(Serializable):
    def __init__(self, token: str, start: int, end: int, limit_exceeded: bool, options: [CompletionOption]=None):
        super().__init__()
        self.token = token
        self.start = start
        self.end = end
        self.limit_exceeded = limit_exceeded
        self.options = options
