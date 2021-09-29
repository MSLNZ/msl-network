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
    # would randomly get the following error when TLS was enabled
    # (on Windows, not sure what happens on POSIX)
    #   ssl.SSLError: [SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC] decryption failed or bad record mac
    # and don't want to test the ssl module here
    manager = conftest.Manager(Echo, disable_tls=True)

    cxn = connect(**manager.kwargs)
    echo = cxn.link('Echo')

    # send a request that is ~110 MB
    args = ['a' * int(1e6), 'b' * int(5e6), 'c' * int(1e7)]
    kwargs = {'1e6': 'x' * int(1e6), '5e6': 'y' * int(5e6),
              'array': list(range(int(1e7)))}
    future1 = echo.echo(*args, asynchronous=True, **kwargs)
    assert isinstance(future1, asyncio.Future)

    # and a few small requests
    future2 = echo.echo('a', asynchronous=True)
    future3 = echo.echo('b', asynchronous=True)

    # and a medium request
    future4 = echo.echo('c', d='d'*int(1e6), asynchronous=True)

    cxn.send_pending_requests()
    assert future1.result() == [args, kwargs]
    assert future2.result() == [['a'], {}]
    assert future3.result() == [['b'], {}]
    assert future4.result() == [['c'], {'d': 'd'*int(1e6)}]

    manager.shutdown(connection=cxn)
