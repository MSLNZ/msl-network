# -*- coding: utf-8 -*-
import os
import sys

from msl.network import json
from msl.network.constants import (
    TERMINATION,
    ENCODING,
)

import pytest
try:
    import orjson
except ImportError:  # 32-bit wheels for orjson are not available on PyPI
    orjson = None

reply = {
    'result': [None, True, 0, 1.2, 'µ', 'text\n{"x":1}\r\ntext',
               '\r', '\n', '{"x":1}\r\n'],
    'requester': 'Client[hostname:55202]',
    'uuid': 'd77540ba-e439-438c-a731-86cc1f105eca',
    'error': False,
}

notification = {
    'result': [[1, 2, 3, '\r', '{"x":1}\n', '7\r\n'],
               {'CR': '\r', 'LF': '\n', 'CRLF': '{"x":1}\r\n'}],
    'service': 'Test',
    'uuid': 'notification',
    'error': False,
}

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
        with pytest.raises(KeyError):
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
    if sys.version_info[:2] > (3, 5):
        # __module__ returns None for Python 3.5
        assert json.backend.loads.__module__ == 'orjson'
        assert json.backend.dumps.__module__ == 'orjson'


@pytest.mark.parametrize(
    'backend',
    ['builtin', 'ujson', 'rapid', 'simple', 'orjson']
)
def test_serialize_deserialize(backend):
    if backend == 'orjson' and orjson is None:
        with pytest.raises(ImportError):
            json.use(backend)
        return

    json.use(backend)

    t = TERMINATION.decode(ENCODING)
    r = json.serialize(reply)
    n = json.serialize(notification)

    assert json.deserialize(r)[0] == reply
    assert json.deserialize(n)[0] == notification

    assert json.deserialize(r+t)[0] == reply
    assert json.deserialize(n+t)[0] == notification

    assert json.deserialize(r+t+t+t)[0] == reply
    assert json.deserialize(n+t+t+t)[0] == notification

    assert json.deserialize(r+t+r) == [reply, reply]
    assert json.deserialize(r+t+r+t) == [reply, reply]
    assert json.deserialize(r+t+r+t+r) == [reply, reply, reply]
    assert json.deserialize(r+t+r+t+r+t) == [reply, reply, reply]

    assert json.deserialize(n+t+n) == [notification, notification]
    assert json.deserialize(n+t+n+t) == [notification, notification]
    assert json.deserialize(n+t+n+t+n) == [notification, notification, notification]
    assert json.deserialize(n+t+n+t+n+t) == [notification, notification, notification]

    s = r+t+n+t+r+t+r+t+n+t+n+t+t+t+r+t
    assert json.deserialize(s) == [reply, notification, reply, reply, notification, notification, reply]

    bad = '{"x":1'
    with pytest.raises(ValueError):
        json.deserialize(s + bad)
    with pytest.raises(ValueError):
        json.deserialize(s + t + bad)
    with pytest.raises(ValueError):
        json.deserialize(s + t + bad + t)


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
        assert json.deserialize('{"x":1}')[0] == {'x': 1}
        assert json.deserialize(b'{"x":1}')[0] == {'x': 1}
        assert json.deserialize(bytearray(b'{"x":1}'))[0] == {'x': 1}
