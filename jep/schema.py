"""JEP message types."""
import enum
from jep.serializer import Serializable

#: Name of token attribute for request/response messages.
TOKEN_ATTR_NAME = 'token'


class Message(Serializable):
    _class_by_name = None

    def invoke(self, listener, context):
        """Dispatch received message to listener. This is the accept() method of the visitor pattern."""
        raise NotImplementedError()

    @classmethod
    def class_by_name(cls, name):
        """Dictionary of known (at least in this module) derived message classes by name."""
        if cls._class_by_name is None:
            # create on demand:
            cls._class_by_name = {sc.__name__: sc for sc in cls.__subclasses__()}
        return cls._class_by_name[name]


class Shutdown(Message):
    def invoke(self, listener, context):
        listener.on_shutdown(context)


class BackendAlive(Message):
    def invoke(self, listener, context):
        listener.on_backend_alive(context)


class ContentSync(Message):
    def __init__(self, file: str, data: str, start: int=0, end: int=None):
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
    debug = 1
    info = 2
    warn = 3
    error = 4
    fatal = 5


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
    def __init__(self, fileProblems: [FileProblems], partial: bool=False):
        super().__init__()
        self.fileProblems = fileProblems
        self.partial = partial

    def invoke(self, listener, context):
        listener.on_problem_update(self, context)


class CompletionRequest(Message):
    def __init__(self, file: str, pos: int, limit: int=None, token: str=None):
        super().__init__()
        self.token = token
        self.file = file
        self.pos = pos
        self.limit = limit

    def invoke(self, listener, context):
        listener.on_completion_request(self, context)


@enum.unique
class SemanticType(enum.Enum):
    comment = 1
    type = 2
    string = 3
    number = 4
    identifier = 5
    keyword = 6
    label = 7
    link = 8
    special1 = 9
    special2 = 10
    special3 = 11
    special4 = 12
    special5 = 13


class CompletionOption(Serializable):
    def __init__(self, insert: str, desc: str=None, longDesc: str=None, semantics: SemanticType=None, extensionId: str=None):
        super().__init__()
        self.insert = insert
        self.desc = desc
        self.longDesc = longDesc
        self.semantics = semantics
        self.extensionId = extensionId


class CompletionResponse(Message):
    def __init__(self, start: int, end: int, limitExceeded: bool=False, options: [CompletionOption]=(), token: str=None):
        super().__init__()
        self.token = token
        self.start = start
        self.end = end
        self.limitExceeded = limitExceeded
        self.options = options

    def invoke(self, listener, context):
        listener.on_completion_response(self, context)


class CompletionInvocation(Message):
    def __init__(self, extensionId: str=None):
        super().__init__()
        self.extensionId = extensionId

    def invoke(self, listener, context):
        listener.on_completion_invocation(self, context)


@enum.unique
class SyntaxFormatType(enum.Enum):
    textmate = 1
    vim = 2


class StaticSyntaxRequest(Message):
    def __init__(self, format: SyntaxFormatType, fileExtensions: [str]=()):
        super().__init__()
        self.format = format
        self.fileExtensions = fileExtensions

    def invoke(self, listener, context):
        listener.on_static_syntax_request(self.format, self.fileExtensions, context)


class StaticSyntax(Serializable):
    def __init__(self, fileExtensions: [str], definition: str):
        super().__init__()
        self.fileExtensions = fileExtensions
        self.definition = definition


class StaticSyntaxList(Message):
    def __init__(self, format: SyntaxFormatType, syntaxes: [StaticSyntax]=()):
        super().__init__()
        self.format = format
        self.syntaxes = syntaxes

    def invoke(self, listener, context):
        listener.on_static_syntax_list(self.format, self.syntaxes, context)
