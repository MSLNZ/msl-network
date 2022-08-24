import os

from msl.network import json

import pytest
try:
    import orjson
except ImportError:  # 32-bit wheels for orjson are not available on PyPI
    orjson = None


initial_backend = json.backend.enum


def setup():
    env = os.getenv('MSL_NETWORK_JSON')
    if env:
        json.use(env)
        assert json.backend.enum == json.Package[env.upper()]
        assert json.backend.enum == initial_backend


def teardown():
    json.use(initial_backend)
    assert json.backend.enum == initial_backend


def test_use_raises():
    with pytest.raises(KeyError):
        json.use('invalid')

    if orjson is None:
        with pytest.raises(ImportError):
            json.use(json.Package.ORJSON)


@pytest.mark.parametrize(
    'backend',
    ['json', 'JsoN', 'builtin', 'BuiLTIn', json.Package.BUILTIN, json.Package.JSON]
)
def test_use_json(backend):
    json.use(backend)
    assert json.backend.name == 'json'
    assert json.backend.loads.__module__ == 'json'
    assert json.backend.dumps.__module__ == 'json'
    assert json.backend.enum == json.Package.BUILTIN


@pytest.mark.parametrize(
    'backend',
    ['ujson', 'UJsON', 'ulTra', 'ULTRA', json.Package.ULTRA, json.Package.UJSON]
)
def test_use_ujson(backend):
    json.use(backend)
    assert json.backend.name == 'ujson'
    assert json.backend.loads.__module__ == 'ujson'
    assert json.backend.dumps.__module__ == 'ujson'
    assert json.backend.enum == json.Package.UJSON


@pytest.mark.parametrize(
    'backend',
    ['simple', 'SImPLE', 'simplejson', 'simpleJSON',
     json.Package.SIMPLE, json.Package.SIMPLEJSON]
)
def test_use_simplejson(backend):
    json.use(backend)
    assert json.backend.name == 'simplejson'
    assert json.backend.loads.__module__ == 'simplejson'
    assert json.backend.dumps.__module__ == 'simplejson'
    assert json.backend.enum == json.Package.SIMPLEJSON


@pytest.mark.parametrize(
    'backend',
    ['rapid', 'RaPiD', 'rapidjson', 'rapidJSON',
     json.Package.RAPID, json.Package.RAPIDJSON]
)
def test_use_rapidjson(backend):
    json.use(backend)
    assert json.backend.name == 'rapidjson'
    assert json.backend.loads.__module__ == 'rapidjson'
    assert json.backend.dumps.__module__ == 'rapidjson'
    assert json.backend.enum == json.Package.RAPIDJSON


@pytest.mark.skipif(orjson is None, reason='orjson is not installed')
@pytest.mark.parametrize(
    'backend',
    ['or', 'orjson', 'Or', 'orJSON', json.Package.OR, json.Package.ORJSON]
)
def test_use_orjson(backend):
    json.use(backend)
    assert json.backend.name == 'orjson'
    assert json.backend.enum == json.Package.ORJSON
    assert json.backend.loads.__module__ == 'orjson'
    assert json.backend.dumps.__module__ == 'orjson'


@pytest.mark.parametrize(
    'backend',
    ['builtin', 'ujson', 'rapid', 'simple', 'orjson']
)
def test_deserialize_types(backend):
    if backend == 'orjson' and orjson is None:
        with pytest.raises(ImportError):
            json.use(backend)
    else:
        json.use(backend)
        assert json.deserialize('{"x":1}') == {'x': 1}
        assert json.deserialize(b'{"x":1}') == {'x': 1}
        assert json.deserialize(bytearray(b'{"x":1}')) == {'x': 1}


@pytest.mark.parametrize(
    'backend',
    ['builtin', 'ujson', 'rapid', 'simple', 'orjson']
)
def test_to_json_attribute(backend):
    class NotSerializable:
        """Does not implement a `to_json()` method."""

        def __init__(self, x):
            self.x = x

    class Serializable:
        """Does implement a `to_json()` method."""

        def __init__(self, z):
            self.z = complex(z)

        def to_json(self):
            return {
                'fruit': ['apple', 'orange', 'pear'],
                'real': self.z.real,
                'imag': self.z.imag,
            }

    if backend == 'orjson' and orjson is None:
        with pytest.raises(ImportError):
            json.use(backend)
    else:
        json.use(backend)

        with pytest.raises(TypeError, match='is not JSON serializable'):
            json.serialize(NotSerializable(1))

        s = json.serialize(Serializable(1+5j))
        assert json.deserialize(s) == {
            'fruit': ['apple', 'orange', 'pear'],
            'real': 1.0,
            'imag': 5.0,
        }
