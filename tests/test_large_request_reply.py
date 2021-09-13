import asyncio

import conftest

from msl.network import connect
from msl.examples.network import Echo


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


def test_asynchronous():
    manager = conftest.Manager(Echo)

    cxn = connect(**manager.kwargs)
    echo = cxn.link('Echo')

    # send a request that is ~110 MB
    args = ['a' * int(1e6), 'b' * int(5e6), 'c' * int(1e7)]
    kwargs = {'1e6': 'x' * int(1e6), '5e6': 'y' * int(5e6),
              'array': list(range(int(1e7))), 'asynchronous': True}
    future = echo.echo(*args, **kwargs)
    assert isinstance(future, asyncio.Future)

    cxn.send_pending_requests()
    reply = future.result()
    kwargs.pop('asynchronous')
    assert reply[0] == args
    assert reply[1] == kwargs

    manager.shutdown(connection=cxn)
