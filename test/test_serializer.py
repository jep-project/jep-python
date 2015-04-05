from .logconfig import configure_test_logger

try:
    import enum
except ImportError:
    import jep.contrib.enum as enum

import inspect
from unittest import mock
from jep.serializer import Serializable, serialize_to_builtins, deserialize_from_builtins


def setup_function(function):
    configure_test_logger()


def test_serializable_meta():
    class A(Serializable):
        def __init__(self,
                     a: int,
                     b: str=mock.sentinel.STR_VALUE,
                     c: [mock.sentinel.LIST_TYPE]=None,
                     d: {mock.sentinel.KEY_TYPE: mock.sentinel.VALUE_TYPE}=None):
            super().__init__()

    # make sure injected attribute list is available at class and instance level and it's the same:
    a = A(mock.sentinel.INT_VALUE)
    assert hasattr(A, 'serialized_attribs')
    assert hasattr(a, 'serialized_attribs')
    assert isinstance(a.serialized_attribs, dict)
    assert A.serialized_attribs is a.serialized_attribs
    assert len(a.serialized_attribs) == 4

    # check type handling:
    assert a.serialized_attribs['a'].name == 'a'
    assert a.serialized_attribs['a'].datatype is int
    assert a.serialized_attribs['a'].default is inspect._empty

    assert a.serialized_attribs['b'].name == 'b'
    assert a.serialized_attribs['b'].datatype is str
    assert a.serialized_attribs['b'].default is mock.sentinel.STR_VALUE

    assert a.serialized_attribs['c'].name == 'c'
    assert a.serialized_attribs['c'].datatype is list
    assert a.serialized_attribs['c'].itemtype is mock.sentinel.LIST_TYPE
    assert a.serialized_attribs['c'].default is None

    assert a.serialized_attribs['d'].name == 'd'
    assert a.serialized_attribs['d'].datatype is dict
    assert a.serialized_attribs['d'].itemtype is mock.sentinel.VALUE_TYPE
    assert a.serialized_attribs['d'].default is None

    # make sure inherited member is still not in serialized list:
    assert 'serialized_attribs' not in a.__dict__


def test_serialize_to_builtins_builtins():
    assert serialize_to_builtins(5) is 5
    assert serialize_to_builtins('a string') is 'a string'
    assert serialize_to_builtins([1, 2, 'a string']) == [1, 2, 'a string']
    assert serialize_to_builtins({1: 'one', 'two': 2}) == {1: 'one', 'two': 2}


def test_serialize_to_builtins_class():
    class A(Serializable):
        def __init__(self, a: int, b: str):
            super().__init__()
            self.a = a
            self.b = b

    a = A(1, 'one')
    expected = {'a': 1, 'b': 'one'}
    assert serialize_to_builtins(a) == expected
    assert serialize_to_builtins([a, a]) == [expected, expected]
    assert serialize_to_builtins({'a': a}) == {'a': expected}


def test_serialize_to_builtins_class_of_class():
    class A(Serializable):
        def __init__(self, a: int, b: str):
            super().__init__()
            self.a = a
            self.b = b

    class B(Serializable):
        def __init__(self, a: A):
            super().__init__()
            self.a = a

    o = B(A(1, 'one'))
    assert serialize_to_builtins(o) == {'a': {'a': 1, 'b': 'one'}}


def test_deserialize_from_builtins_builtins():
    assert deserialize_from_builtins(5, int) is 5
    assert deserialize_from_builtins('one', str) is 'one'
    assert deserialize_from_builtins([1, 2, 3], list, int) == [1, 2, 3]
    assert deserialize_from_builtins({1: 'one', 2: 'two'}, dict, str) == {1: 'one', 2: 'two'}


def test_deserialize_from_builtins_class():
    class A(Serializable):
        def __init__(self, a: int, b: str):
            super().__init__()
            self.a = a
            self.b = b

        def __eq__(self, other):
            return self.a == other.a and self.b == other.b

    s = {'a': 1, 'b': 'one'}
    expected = A(1, 'one')
    assert deserialize_from_builtins(s, A) == expected

    # currently not supported (no explicit attribute information):
    # assert Serializer.deserialize_from_builtins([s, s], A) == [expected, expected]
    # assert Serializer.deserialize_from_builtins({1: s}, A) == [1, expected]


def test_deserialize_from_builtins_class_of_class():
    class A(Serializable):
        def __init__(self, a: int, b: str):
            super().__init__()
            self.a = a
            self.b = b

        def __eq__(self, other):
            return self.a == other.a and self.b == other.b

    class B(Serializable):
        def __init__(self, a_list: [A], a_dict: {int: A}):
            super().__init__()
            self.a_list = a_list
            self.a_dict = a_dict

        def __eq__(self, other):
            return self.a_dict == other.a_dict and self.a_list == other.a_list

    assert deserialize_from_builtins(
        {
            'a_list': [{'a': 1, 'b': 'one'}, {'a': 2, 'b': 'two'}],
            'a_dict': {1: {'a': 1, 'b': 'one'}, 2: {'a': 2, 'b': 'two'}}
        }, B) == B([A(1, 'one'), A(2, 'two')], {1: A(1, 'one'), 2: A(2, 'two')})


def test_serialize_to_builtins_default_values_not_contained():
    class A(Serializable):
        def __init__(self, a: int=42, b: str='forty-two'):
            super().__init__()
            self.a = a
            self.b = b

    o = A()

    # no entries in dictionary as only defaults are contained:
    assert len(serialize_to_builtins(o)) == 0


def test_deserialize_from_buitlins_default_value():
    class A(Serializable):
        def __init__(self, a: int=42, b: str='forty-two'):
            super().__init__()
            self.a = a
            self.b = b

        def __eq__(self, other):
            return self.a == other.a and self.b == other.b

    a = deserialize_from_builtins({}, A)
    assert a == A()
    assert a.a is 42
    assert a.b == 'forty-two'


def test_serialize_to_builtins_none():
    assert serialize_to_builtins(None) is None


def test_deserialize_from_builtins_none():
    assert deserialize_from_builtins(None, None) is None


def test_serialize_to_builtins_enum():
    class MyEnum(enum.Enum):
        Literal1 = 1
        Literal2 = 2

    assert serialize_to_builtins(MyEnum.Literal1) == 'Literal1'


def test_deserialize_from_builtins_enum():
    class MyEnum(enum.Enum):
        Literal1 = 1
        Literal2 = 2

    assert deserialize_from_builtins('Literal2', MyEnum) == MyEnum.Literal2


def test_serializable_is_serialized_and_not_default():
    class A(Serializable):
        def __init__(self, a: int=42, b: str='forty-two'):
            super().__init__()
            self.a = a
            self.b = b

    o = A()
    assert not o.is_serialized_and_not_default('c', 42)
    assert o.is_serialized_and_not_default('a', 5)
    assert not o.is_serialized_and_not_default('a', 42)
    assert o.is_serialized_and_not_default('b', 'other value')
    assert not o.is_serialized_and_not_default('b', 'forty-two')
