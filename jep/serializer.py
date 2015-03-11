"""Reflective serialization of messages."""
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
            self.datatype = annotation[0]
        elif isinstance(annotation, dict):
            assert len(annotation) == 1, "Type annotation for dict must contain a single map to item type, e.g. {int: str}."
            self.datatype = list(annotation.values())[0]
        else:
            self.datatype = annotation


class SerializableMeta(type):
    """Metaclass remembering the types and default values passed to class constructors."""

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        ctor = inspect.signature(cls.__init__)
        cls.serialized_attribs = [SerializedAttribute(p.name, p.annotation, p.default) for p in ctor.parameters.values() if p.name is not 'self']
        return cls


def serialize_to_builtins(o):
    """Serialization of arbitrary object to built-in data types."""

    if hasattr(o, '__dict__'):
        serialized = serialize_to_builtins(o.__dict__)
    elif isinstance(o, list):
        serialized = [serialize_to_builtins(item) for item in o]
    elif isinstance(o, dict):
        serialized = {key: serialize_to_builtins(value) for key, value in o.items()}
    else:
        serialized = o

    return serialized


def deserialize_from_builtins(serialized, datatype):
    """Instantiation of data type from built-in serialized form."""

    if serialized is None:
        instantiated = None
    elif isinstance(datatype, SerializableMeta):
        ctor_arguments = {attrib.name: deserialize_from_builtins(serialized.get(attrib.name, attrib.default), attrib.datatype)
                          for attrib in datatype.serialized_attribs}
        instantiated = datatype(**ctor_arguments)
    elif isinstance(serialized, list):
        instantiated = [deserialize_from_builtins(item, datatype) for item in serialized]
    elif isinstance(serialized, dict):
        instantiated = {key: deserialize_from_builtins(value, datatype) for key, value in serialized.items()}
    else:
        instantiated = serialized

    return instantiated