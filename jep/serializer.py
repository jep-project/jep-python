"""Reflective serialization of messages based on mapping classes to built-in types."""
from enum import Enum
import inspect


class SerializedAttribute:
    """Description of constructor attribute to be serialized as member of object."""

    def __init__(self, name, annotation, default):
        self.name = name
        self.default = default

        # original annotation for debugging:
        self.annotation = annotation

        # derive data type from annotation, for collections store item type:
        if isinstance(annotation, list):
            assert len(annotation) == 1, "Type annotation for list must contain a single item type, e.g. [int]."
            self.datatype = list
            self.itemtype = annotation[0]
        elif isinstance(annotation, dict):
            assert len(annotation) == 1, "Type annotation for dict must contain a single map to item type, e.g. {int: str}."
            self.datatype = dict
            self.itemtype = list(annotation.values())[0]
        else:
            self.datatype = annotation
            self.itemtype = None


class SerializableMeta(type):
    """Metaclass remembering the types and default values passed to class constructors."""

    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        ctor = inspect.signature(cls.__init__)
        cls.serialized_attribs = {p.name: SerializedAttribute(p.name, p.annotation, p.default) for p in ctor.parameters.values() if p.name is not 'self'}


class Serializable(metaclass=SerializableMeta):
    """Base class for classes to be serialized to and from built-in types."""

    #: List of attributes to be processed during serialization.
    serialized_attribs = None

    def __init__(self):
        # hide base class init arguments to prevent they are collected:
        super().__init__()

    @classmethod
    def is_serialized_and_not_default(cls, name, value):
        """Checks if attribute with given name has a value different from its optional default."""
        if not cls.serialized_attribs:
            return False

        attrib = cls.serialized_attribs.get(name, None)
        return attrib and ((attrib.default is inspect._empty) or (attrib.default != value))


def serialize_to_builtins(o):
    """Serialization of arbitrary object to built-in data types."""

    if isinstance(o, Enum):
        serialized = o.name
    elif isinstance(o, Serializable):
        serialized = serialize_to_builtins({key: value for key, value in o.__dict__.items() if o.is_serialized_and_not_default(key, value)})
    elif hasattr(o, '__dict__'):
        serialized = serialize_to_builtins(o.__dict__)
    elif isinstance(o, list):
        serialized = [serialize_to_builtins(item) for item in o]
    elif isinstance(o, dict):
        serialized = {key: serialize_to_builtins(value) for key, value in o.items()}
    else:
        serialized = o

    return serialized


def deserialize_from_builtins(serialized, datatype, itemtype=None):
    """Instantiation of data type from built-in serialized form."""

    if serialized is None:
        instantiated = None
    elif isinstance(datatype, SerializableMeta):
        ctor_arguments = {attrib.name: deserialize_from_builtins(serialized.get(attrib.name, attrib.default), attrib.datatype, attrib.itemtype)
                          for attrib in datatype.serialized_attribs.values()}
        instantiated = datatype(**ctor_arguments)
    elif datatype is list and itemtype:
        instantiated = [deserialize_from_builtins(item, itemtype) for item in serialized]
    elif datatype is dict and itemtype:
        instantiated = {key: deserialize_from_builtins(value, itemtype) for key, value in serialized.items()}
    elif issubclass(datatype, Enum):
        instantiated = datatype[serialized]
    elif not itemtype:
        instantiated = datatype(serialized)
    else:
        raise TypeError("Cannot deserialize type %s with item type %s." % (datatype, itemtype))

    return instantiated