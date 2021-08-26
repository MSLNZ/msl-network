# -*- coding: utf-8 -*-
import sys

from msl.network import json
from msl.network.constants import TERMINATION

import pytest

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


def teardown():
    json.use(json.Package.BUILTIN)


def test_set():
    assert json.backend.loads
    assert json.backend.dumps
    assert json.backend.name

    with pytest.raises(KeyError):
        json.use('invalid')

    for item in ('builtin', 'BuiLTIn', json.Package.BUILTIN):
        json.use(item)
        assert json.backend.name == 'json'
        assert json.backend.loads.__module__ == 'json'
        assert json.backend.dumps.__module__ == 'json'

    for item in ('ujson', 'UJsON', 'ultra', 'ULTRA', json.Package.ULTRA, json.Package.UJSON):
        json.use(item)
        assert json.backend.name == 'ujson'
        assert json.backend.loads.__module__ == 'ujson'
        assert json.backend.dumps.__module__ == 'ujson'

    for item in ('simple', 'SImPLE', json.Package.SIMPLE):
        json.use(item)
        assert json.backend.name == 'simplejson'
        assert json.backend.loads.__module__ == 'simplejson'
        assert json.backend.dumps.__module__ == 'simplejson'

    for item in ('rapid', 'RaPiD', json.Package.RAPID):
        json.use(item)
        assert json.backend.name == 'rapidjson'
        assert json.backend.loads.__module__ == 'rapidjson'
        assert json.backend.dumps.__module__ == 'rapidjson'

    for item in ('or', 'orjson', 'Or', 'orJSON', json.Package.OR, json.Package.ORJSON):
        json.use(item)
        assert json.backend.name == 'orjson'
        if sys.version_info[:2] > (3, 5):
            # __module__ returns None for Python 3.5
            assert json.backend.loads.__module__ == 'orjson'
            assert json.backend.dumps.__module__ == 'orjson'


@pytest.mark.parametrize('backend', ('builtin', 'ujson', 'rapid', 'simple', 'orjson'))
def test_serialize_deserialize(backend):
    json.use(backend)

    t = TERMINATION.decode()
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


@pytest.mark.parametrize('backend', ('builtin', 'ujson', 'rapid', 'simple', 'orjson'))
def test_deserialize_types(backend):
    json.use(backend)
    assert json.deserialize('{"x":1}')[0] == {'x': 1}
    assert json.deserialize(b'{"x":1}')[0] == {'x': 1}
    assert json.deserialize(bytearray(b'{"x":1}'))[0] == {'x': 1}
