import os

import pytest

from msl.network import json

try:
    import orjson
except ImportError:  # 32-bit wheels for orjson are not available on PyPI
    orjson = None


initial_backend = json._backend.enum  # noqa: Accessing protected member _backend


class Complex:
    """Implement a `to_json()` method to make it JSON serializable."""

    def __init__(self, real, imag):
        self.z = complex(real, imag)

    def to_json(self):
        return {'real': self.z.real, 'imag': self.z.imag}


def setup():
    env = os.getenv('MSL_NETWORK_JSON')
    if env:
        json.use(env)
        assert json._backend.enum == json.Package[env.upper()]  # noqa
        assert json._backend.enum == initial_backend  # noqa


def teardown():
    json.use(initial_backend)
    assert json._backend.enum == initial_backend  # noqa: Accessing protected member _backend


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
    assert json._backend.name == 'json'
    assert json._backend.loads.__module__ == 'json'
    assert json._backend.dumps.__module__ == 'json'
    assert json._backend.enum == json.Package.BUILTIN
    assert json.deserialize(json.serialize(Complex(4, 3))) == {'real': 4.0, 'imag': 3.0}


@pytest.mark.parametrize(
    'backend',
    ['ujson', 'UJsON', 'ulTra', 'ULTRA', json.Package.ULTRA, json.Package.UJSON]
)
def test_use_ujson(backend):
    json.use(backend)
    assert json._backend.name == 'ujson'
    assert json._backend.loads.__module__ == 'ujson'
    assert json._backend.dumps.__module__ == 'ujson'
    assert json._backend.enum == json.Package.UJSON
    assert json.deserialize(json.serialize(Complex(4, 3))) == {'real': 4.0, 'imag': 3.0}


@pytest.mark.parametrize(
    'backend',
    ['simple', 'SImPLE', 'simplejson', 'simpleJSON',
     json.Package.SIMPLE, json.Package.SIMPLEJSON]
)
def test_use_simplejson(backend):
    json.use(backend)
    assert json._backend.name == 'simplejson'
    assert json._backend.loads.__module__ == 'simplejson'
    assert json._backend.dumps.__module__ == 'simplejson'
    assert json._backend.enum == json.Package.SIMPLEJSON
    assert json.deserialize(json.serialize(Complex(4, 3))) == {'real': 4.0, 'imag': 3.0}


@pytest.mark.parametrize(
    'backend',
    ['rapid', 'RaPiD', 'rapidjson', 'rapidJSON',
     json.Package.RAPID, json.Package.RAPIDJSON]
)
def test_use_rapidjson(backend):
    json.use(backend)
    assert json._backend.name == 'rapidjson'
    assert json._backend.loads.__module__ == 'rapidjson'
    assert json._backend.dumps.__module__ == 'rapidjson'
    assert json._backend.enum == json.Package.RAPIDJSON
    assert json.deserialize(json.serialize(Complex(4, 3))) == {'real': 4.0, 'imag': 3.0}


@pytest.mark.skipif(orjson is None, reason='orjson is not installed')
@pytest.mark.parametrize(
    'backend',
    ['or', 'orjson', 'Or', 'orJSON', json.Package.OR, json.Package.ORJSON]
)
def test_use_orjson(backend):
    json.use(backend)
    assert json._backend.name == 'orjson'
    assert json._backend.enum == json.Package.ORJSON
    assert json._backend.loads.__module__ == 'orjson'
    assert json._backend.dumps.__module__ == 'orjson'
    assert json.deserialize(json.serialize(Complex(4, 3))) == {'real': 4.0, 'imag': 3.0}


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
def test_use_kwargs(backend):
    if backend == 'orjson' and orjson is None:
        with pytest.raises(ImportError):
            json.use(backend)
    else:
        json.use(json.Package.BUILTIN,
                 dumps_kwargs={'unsupported': True},
                 loads_kwargs={'doesnotexist': False})

        assert json._backend.name == 'json'
        assert json._backend.loads.__module__ == 'json'
        assert json._backend.dumps.__module__ == 'json'
        assert json._backend.enum == json.Package.BUILTIN
        assert json._backend.dumps_kwargs == {'unsupported': True}
        assert json._backend.loads_kwargs == {'doesnotexist': False}

        with pytest.raises(TypeError, match=r"keyword argument 'unsupported'"):
            json.serialize({'x': 1})

        with pytest.raises(TypeError, match=r"keyword argument 'doesnotexist'"):
            json.deserialize('{"x":1}')
