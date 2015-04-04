"""JEP message types."""
try:
    import enum
except ImportError:
    import jep.contrib.enum as enum

from jep.serializer import Serializable


class Message(Serializable):
    def invoke(self, listener, context):
        """Dispatch received message to listener. This is the accept() method of the visitor pattern."""
        raise NotImplementedError()


class Shutdown(Message):
    def invoke(self, listener, context):
        listener.on_shutdown(context)


class BackendAlive(Message):
    def invoke(self, listener, context):
        listener.on_backend_alive(context)


class ContentSync(Message):
    def __init__(self, file: str, data: bytes, start: int=0, end: int=-1):
        super().__init__()
        self.file = file
        self.start = start
        self.end = end
        self.data = data

    def invoke(self, listener, context):
        listener.on_content_sync(self, context)


class OutOfSync(Message):
    def __init__(self, file: str):
        super().__init__()
        self.file = file

    def invoke(self, listener, context):
        listener.on_out_of_sync(self, context)


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


class ProblemUpdate(Message):
    def __init__(self, file_problems: [FileProblems], partial: bool=False):
        super().__init__()
        self.file_problems = file_problems
        self.partial = partial

    def invoke(self, listener, context):
        listener.on_problem_update(self, context)


class CompletionRequest(Message):
    def __init__(self, token: str, file: str, pos: int, limit: int=None):
        super().__init__()
        self.token = token
        self.file = file
        self.pos = pos
        self.limit = limit

    def invoke(self, listener, context):
        listener.on_completion_request(self, context)


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
    def __init__(self, insert: str, desc: str=None, long_desc: str=None, semantics: SemanticType=None, extension_id: str=None):
        super().__init__()
        self.insert = insert
        self.desc = desc
        self.long_desc = long_desc
        self.semantics = semantics
        self.extension_id = extension_id


class CompletionResponse(Message):
    def __init__(self, token: str, start: int, end: int, limit_exceeded: bool, options: [CompletionOption]=None):
        super().__init__()
        self.token = token
        self.start = start
        self.end = end
        self.limit_exceeded = limit_exceeded
        self.options = options

    def invoke(self, listener, context):
        listener.on_completion_response(self, context)


class CompletionInvocation(Message):
    def __init__(self, extension_id):
        super().__init__()
        self.extension_id = extension_id

    def invoke(self, listener, context):
        listener.on_completion_invocation(self, context)
