import inspect
from unittest import mock
from jep.serializer import SerializableMeta, serialize_to_builtins, deserialize_from_builtins


def test_serializable_meta():
    class A(metaclass=SerializableMeta):
        def __init__(self,
                     a: int,
                     b: str=mock.sentinel.STR_VALUE,
                     c: [mock.sentinel.LIST_TYPE]=None,
                     d: {mock.sentinel.KEY_TYPE: mock.sentinel.VALUE_TYPE}=None):
            pass

    # make sure injected attribute list is available at class and instance level and it's the same:
    a = A(mock.sentinel.INT_VALUE)
    assert hasattr(A, 'serialized_attribs')
    assert hasattr(a, 'serialized_attribs')
    assert isinstance(a.serialized_attribs, list)
    assert A.serialized_attribs is a.serialized_attribs

    # check type handling:
    assert a.serialized_attribs[0].name == 'a'
    assert a.serialized_attribs[0].datatype is int
    assert a.serialized_attribs[0].default is inspect._empty

    assert a.serialized_attribs[1].name == 'b'
    assert a.serialized_attribs[1].datatype is str
    assert a.serialized_attribs[1].default is mock.sentinel.STR_VALUE

    assert a.serialized_attribs[2].name == 'c'
    assert a.serialized_attribs[2].datatype is mock.sentinel.LIST_TYPE
    assert a.serialized_attribs[2].default is None

    assert a.serialized_attribs[3].name == 'd'
    assert a.serialized_attribs[3].datatype is mock.sentinel.VALUE_TYPE
    assert a.serialized_attribs[3].default is None


def test_serialize_to_builtins_builtins():
    assert serialize_to_builtins(5) is 5
    assert serialize_to_builtins('a string') is 'a string'
    assert serialize_to_builtins([1, 2, 'a string']) == [1, 2, 'a string']
    assert serialize_to_builtins({1: 'one', 'two': 2}) == {1: 'one', 'two': 2}


def test_serialize_to_builtins_class():
    class A(metaclass=SerializableMeta):
        def __init__(self, a: int, b: str):
            self.a = a
            self.b = b

    a = A(1, 'one')
    expected = {'a': 1, 'b': 'one'}
    assert serialize_to_builtins(a) == expected
    assert serialize_to_builtins([a, a]) == [expected, expected]
    assert serialize_to_builtins({'a': a}) == {'a': expected}


def test_serialize_to_builtins_class_of_class():
    class A(metaclass=SerializableMeta):
        def __init__(self, a: int, b: str):
            self.a = a
            self.b = b

    class B(metaclass=SerializableMeta):
        def __init__(self, a: A):
            self.a = a

    o = B(A(1, 'one'))
    assert serialize_to_builtins(o) == {'a': {'a': 1, 'b': 'one'}}


def test_deserialize_from_builtins_builtins():
    assert deserialize_from_builtins(5, int) is 5
    assert deserialize_from_builtins('one', str) is 'one'
    assert deserialize_from_builtins([1, 2, 3], int) == [1, 2, 3]
    assert deserialize_from_builtins({1: 'one', 2: 'two'}, str) == {1: 'one', 2: 'two'}


def test_deserialize_from_builtins_class():
    class A(metaclass=SerializableMeta):
        def __init__(self, a: int, b: str):
            self.a = a
            self.b = b

        def __eq__(self, other):
            return self.a == other.a and self.b == other.b

    s = {'a': 1, 'b': 'one'}
    expected = A(1, 'one')
    assert deserialize_from_builtins(s, A) == expected

    # currently not supported (no explicit attribute information):
    # assert deserialize_from_builtins([s, s], A) == [expected, expected]
    # assert deserialize_from_builtins({1: s}, A) == [1, expected]


def test_deserialize_from_builtins_class_of_class():
    class A(metaclass=SerializableMeta):
        def __init__(self, a: int, b: str):
            self.a = a
            self.b = b

        def __eq__(self, other):
            return self.a == other.a and self.b == other.b

    class B(metaclass=SerializableMeta):
        def __init__(self, a_list: [A], a_dict: {int: A}):
            self.a_list = a_list
            self.a_dict = a_dict

        def __eq__(self, other):
            return self.a_dict == other.a_dict and self.a_list == other.a_list

    assert deserialize_from_builtins({
        'a_list': [{'a': 1, 'b': 'one'}, {'a': 2, 'b': 'two'}],
        'a_dict': {1: {'a': 1, 'b': 'one'}, 2: {'a': 2, 'b': 'two'}}
    }, B) == B([A(1, 'one'), A(2, 'two')], {1: A(1, 'one'), 2: A(2, 'two')})

