import sys
import concurrent.futures

import pytest

import conftest

from msl.network import connect
from msl.examples.network import Echo

skipif_32bit = pytest.mark.skipif(
    sys.maxsize < 2**32,
    reason='ignore on 32-bit platform'
)


@skipif_32bit
def test_synchronous():
    manager = conftest.Manager(Echo)

    cxn = connect(**manager.kwargs)
    echo = cxn.link('Echo')

    # send a request that is ~110 MB
    args = ['a' * int(1e6), 'b' * int(5e6), 'c' * int(1e7)]
    kwargs = {'1e6': 'x' * int(1e6), '5e6': 'y' * int(5e6),
              'array': list(range(int(1e7)))}
    reply = echo.echo(*args, **kwargs)
    assert reply[0] == args
    assert reply[1] == kwargs

    manager.shutdown(connection=cxn)


@skipif_32bit
def test_asynchronous():
    manager = conftest.Manager(Echo)

    cxn = connect(**manager.kwargs)
    echo = cxn.link('Echo')

    # send a request that is ~110 MB
    args = ['a' * int(1e6), 'b' * int(5e6), 'c' * int(1e7)]
    kwargs = {'1e6': 'x' * int(1e6), '5e6': 'y' * int(5e6),
              'array': list(range(int(1e7)))}
    future1 = echo.echo(*args, asynchronous=True, **kwargs)

    # a few small requests
    future2 = echo.echo('a', asynchronous=True)
    future3 = echo.echo(data=list(range(10)), asynchronous=True)

    # and a medium request
    future4 = echo.echo(-2, -1, 0, q='q'*int(1e6), asynchronous=True)

    assert isinstance(future1, concurrent.futures.Future)
    assert isinstance(future2, concurrent.futures.Future)
    assert isinstance(future3, concurrent.futures.Future)
    assert isinstance(future4, concurrent.futures.Future)

    assert future1.result(30) == [args, kwargs]
    assert future2.result(30) == [['a'], {}]
    assert future3.result(30) == [[], {'data': list(range(10))}]
    assert future4.result(30) == [[-2, -1, 0], {'q': 'q'*int(1e6)}]

    manager.shutdown(connection=cxn)
