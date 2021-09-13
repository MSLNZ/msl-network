import time
import math
import asyncio

from pytest import approx, raises

import conftest

from msl.network import connect
from msl.network.exceptions import MSLNetworkError
from msl.examples.network import BasicMath, MyArray, Echo


def test_echo():
    manager = conftest.Manager(Echo)

    cxn = connect(**manager.kwargs)

    echo = cxn.link('Echo')

    args, kwargs = echo.echo(1, 2, 3)
    assert len(args) == 3
    assert args[0] == 1
    assert args[1] == 2
    assert args[2] == 3
    assert len(kwargs) == 0

    args, kwargs = echo.echo(x=4, y=5, z=6)
    assert len(args) == 0
    assert kwargs['x'] == 4
    assert kwargs['y'] == 5
    assert kwargs['z'] == 6

    args, kwargs = echo.echo(1, 2, 3, x=4, y=5, z=6)
    assert len(args) == 3
    assert args[0] == 1
    assert args[1] == 2
    assert args[2] == 3
    assert kwargs['x'] == 4
    assert kwargs['y'] == 5
    assert kwargs['z'] == 6

    manager.shutdown(connection=cxn)


def test_asynchronous_synchronous_simultaneous():
    manager = conftest.Manager(BasicMath)

    cxn = connect(**manager.kwargs)

    bm = cxn.link('BasicMath')

    add = bm.add(1, 1, asynchronous=True)
    assert isinstance(add, asyncio.Future)

    # send a synchronous request without sending the asynchronous request
    with raises(ValueError):
        bm.subtract(1, 1)

    cxn.send_pending_requests()
    assert add.result() == 2

    # now we can send a synchronous request
    assert bm.subtract(1, 1) == 0

    manager.shutdown(connection=cxn)


def test_basic_math_synchronous():
    manager = conftest.Manager(BasicMath)

    cxn = connect(**manager.kwargs)

    bm = cxn.link('BasicMath')

    # since we are executing the commands synchronously we expect
    # more than this many seconds to pass to execute all commands below
    minimum_dt = sum(list(range(7)))

    t0 = time.perf_counter()

    assert bm.euler() == approx(math.exp(1))
    assert bm.pi() == approx(math.pi)
    assert bm.add(14.5, 8.9) == approx(14.5 + 8.9)
    assert bm.subtract(1013, 87245) == 1013 - 87245
    assert bm.multiply(5.3, 5.4) == approx(5.3 * 5.4)
    assert bm.divide(2.2, 6.1) == approx(2.2 / 6.1)
    assert bm.ensure_positive(1)
    with raises(MSLNetworkError):
        bm.ensure_positive(-1)
    assert bm.power(-3.14, 5) == approx(-3.14**5)

    assert time.perf_counter() - t0 > minimum_dt

    manager.shutdown(connection=cxn)


def test_basic_math_asynchronous():
    manager = conftest.Manager(BasicMath)

    cxn = connect(**manager.kwargs)
    bm = cxn.link('BasicMath')

    # since we are executing the commands asynchronously we expect all
    # commands to finish within the sleep time of the BasicMath.power() method
    # expect 6 seconds using asynchronous and 1+2+3+4+5+6=21 seconds for synchronous calls
    # picked a number close to 6 seconds
    maximum_dt = 8

    euler = bm.euler(asynchronous=True)
    pi = bm.pi(asynchronous=True)
    add = bm.add(451.57, -745.12, asynchronous=True)
    subtract = bm.subtract(-99.82, -872.45, asynchronous=True)
    multiply = bm.multiply(-53.33, 54.44, asynchronous=True)
    divide = bm.divide(4.2, 19.3, asynchronous=True)
    err = bm.ensure_positive(10, asynchronous=True)
    power = bm.power(123.45, 3, asynchronous=True)

    t0 = time.perf_counter()
    cxn.send_pending_requests()
    assert time.perf_counter() - t0 < maximum_dt

    assert euler.result() == approx(math.exp(1))
    assert pi.result() == approx(math.pi)
    assert add.result() == approx(451.57 - 745.12)
    assert subtract.result() == approx(-99.82 + 872.45)
    assert multiply.result() == approx(-53.33 * 54.44)
    assert divide.result() == approx(4.2 / 19.3)
    assert err.result()
    assert power.result() == approx(123.45 ** 3)

    manager.shutdown(connection=cxn)


def test_array_synchronous():
    manager = conftest.Manager(MyArray)

    cxn = connect(**manager.kwargs)

    array = cxn.link('MyArray')
    out1 = array.linspace(-1, 1, 100)
    assert len(out1) == 100
    assert out1[0] == approx(-1)
    assert out1[-1] == approx(1)

    out2 = array.scalar_multiply(-2, out1)
    assert len(out2) == 100
    assert out2[0] == approx(2)
    assert out2[-1] == approx(-2)

    manager.shutdown(connection=cxn)


def test_basic_math_and_array_asynchronous():

    manager = conftest.Manager(BasicMath, MyArray)

    cxn = connect(**manager.kwargs)

    bm = cxn.link('BasicMath')
    array = cxn.link('MyArray')

    power = bm.power(math.pi, math.exp(1), asynchronous=True)
    linspace = array.linspace(0, 1, 1e6, asynchronous=True)

    cxn.send_pending_requests()

    assert power.result() == approx(math.pi ** math.exp(1))
    assert len(linspace.result()) == 1e6

    manager.shutdown(connection=cxn)


def test_spawn_basic_math_and_array_asynchronous():

    manager = conftest.Manager(BasicMath, MyArray)

    cxn1 = connect(**manager.kwargs)
    cxn2 = cxn1.spawn()

    bm = cxn1.link('BasicMath')
    array = cxn2.link('MyArray')

    power = bm.power(math.pi, math.exp(1), asynchronous=True)
    linspace = array.linspace(0, 1, 1e6, asynchronous=True)

    cxn1.send_pending_requests()
    cxn2.send_pending_requests()

    assert power.result() == approx(math.pi ** math.exp(1))
    assert len(linspace.result()) == 1e6

    assert cxn2.address_manager is not None
    assert cxn2.port is not None

    manager.shutdown(connection=cxn1)

    # shutting down the manager using cxn1 will also disconnect cxn2
    assert cxn2.address_manager is None
    assert cxn2.port is None


def test_private_retrieval():
    manager = conftest.Manager(BasicMath)

    cxn = connect(**manager.kwargs)
    bm = cxn.link('BasicMath')

    assert bm.password('any name') != manager.admin_password
    with raises(MSLNetworkError):
        bm._password()

    manager.shutdown(connection=cxn)


def test_basic_math_timeout_synchronous():
    manager = conftest.Manager(BasicMath)
    cxn = connect(**manager.kwargs)
    bm = cxn.link('BasicMath')

    a, b = 2, 10

    # no timeout specified
    assert bm.add(a, b) == a+b
    assert bm.power(a, b) == a**b

    # the `add` method sleeps for 1 second -> no timeout expected
    assert bm.add(a, b, timeout=3) == a+b

    # the `power` method sleeps for 6 seconds -> timeout expected
    with raises(TimeoutError):
        bm.power(a, b, timeout=3)

    manager.shutdown(connection=cxn)


def test_basic_math_timeout_asynchronous():
    manager = conftest.Manager(BasicMath)
    cxn = connect(**manager.kwargs)
    bm = cxn.link('BasicMath')

    a, b = 2, 10

    add_1 = bm.add(a, b, asynchronous=True)
    power_1 = bm.power(a, b, asynchronous=True)

    # no timeout specified
    cxn.send_pending_requests()
    assert add_1.result() == a+b
    assert power_1.result() == a**b

    # the `add` method sleeps for 1 second -> no timeout expected
    # the `power` method sleeps for 6 seconds -> timeout expected

    add_2 = bm.add(a, b, asynchronous=True)
    power_2 = bm.power(a, b, asynchronous=True)
    with raises(TimeoutError):
        # must wait for all futures to finish, so the `power` method is taking too long
        cxn.send_pending_requests(timeout=3)

    manager.shutdown(connection=cxn)


def test_echo_json_not_serializable_synchronous():
    manager = conftest.Manager(Echo)
    cxn = connect(**manager.kwargs)

    e = cxn.link('Echo')

    # make sure that this is okay
    a, k = e.echo('hello', x=1)
    assert a[0] == 'hello'
    assert k['x'] == 1

    # send a complex number
    with raises(TypeError, match=r'not JSON serializable'):
        e.echo(1+2j)

    # make sure that the cxn._futures dict is empty so that we can send a valid request
    a, k = e.echo(1)
    assert a[0] == 1
    assert not k

    manager.shutdown(connection=cxn)


def test_echo_json_not_serializable_asynchronous():
    manager = conftest.Manager(Echo)
    cxn = connect(**manager.kwargs)

    e = cxn.link('Echo')

    # make sure that this is okay
    future = e.echo('hello', x=1, asynchronous=True)
    cxn.send_pending_requests()
    a, k, = future.result()
    assert a[0] == 'hello'
    assert k['x'] == 1

    # send a complex number
    future = e.echo(1+2j, asynchronous=True)
    with raises(TypeError, match=r'not JSON serializable'):
        cxn.send_pending_requests()

    # make sure that the cxn._futures dict is empty so that we can send a valid request
    future = e.echo(1, asynchronous=True)
    cxn.send_pending_requests()
    a, k, = future.result()
    assert a[0] == 1
    assert not k

    manager.shutdown(connection=cxn)


def test_cannot_specify_multiple_passwords():
    echo = Echo()
    with raises(ValueError):
        echo.start(password='abc', password_manager='xyz')


def test_max_clients():
    # no limit
    manager = conftest.Manager(Echo)
    cxn = connect(**manager.kwargs)
    spawns, links = [], []
    for i in range(40):  # pretend that 40 == infinity (approximately the limit for macOS)
        spawns.append(cxn.spawn('Client%d' % i))
        links.append(spawns[-1].link('Echo'))
        assert links[-1].echo(i)[0][0] == i
    assert len(cxn.manager()['clients']) == len(spawns) + 1
    for spawn in spawns:
        spawn.disconnect()
    manager.shutdown(connection=cxn)

    # only 1 Client at a time
    manager = conftest.Manager(Echo, BasicMath, max_clients=1)
    client1 = connect(**manager.kwargs)
    echo1 = client1.link('Echo')
    assert echo1.echo('abc123')[0][0] == 'abc123'
    math1 = client1.link('BasicMath')
    assert math1.add(5, -3) == 2
    client2 = client1.spawn('Client2')
    with raises(MSLNetworkError, match=r'PermissionError: The maximum number of Clients'):
        client2.link('Echo')
    with raises(MSLNetworkError, match=r'PermissionError: The maximum number of Clients'):
        client2.link('BasicMath')
    client1.disconnect()  # Echo and BasicMath are no longer linked with client1
    echo2 = client2.link('Echo')
    assert echo2.echo(9.9)[0][0] == 9.9
    math2 = client2.link('BasicMath')
    assert math2.add(9, 5) == 14
    manager.shutdown(connection=client2)

    # only 5 Clients at a time
    manager = conftest.Manager(Echo, max_clients=5)
    cxn = connect(**manager.kwargs)
    spawns, links = [], []
    for i in range(5):
        spawns.append(cxn.spawn('Client%d' % i))
        links.append(spawns[-1].link('Echo'))
        assert links[-1].echo(i)[0][0] == i
    client6 = cxn.spawn('Client6')
    with raises(MSLNetworkError, match=r'PermissionError: The maximum number of Clients'):
        client6.link('Echo')
    assert len(cxn.manager()['clients']) == len(spawns) + 2
    for spawn in spawns:
        spawn.disconnect()
    client6.disconnect()
    manager.shutdown(connection=cxn)

    # the same Client link multiple times to the same Service
    manager = conftest.Manager(Echo, max_clients=1)
    cxn = connect(**manager.kwargs)
    link1 = cxn.link('Echo')
    assert link1.echo('foo')[0][0] == 'foo'
    link2 = cxn.link('Echo')
    assert link2.echo('bar')[0][0] == 'bar'
    manager.shutdown(connection=cxn)


def test_ignore_attributes():
    manager = conftest.Manager(MyArray, ignore_attributes=['linspace'])
    cxn = connect(**manager.kwargs)

    # 'linspace' is not a publicly known attribute
    identity = cxn.manager()['services']['MyArray']
    assert 'linspace' not in identity['attributes']
    assert 'scalar_multiply' in identity['attributes']

    my_array = cxn.link('MyArray')

    # however, 'linspace' is accessible
    result = my_array.linspace(0, 1, n=10)
    assert len(result) == 10
    expected = [i*1./9. for i in range(10)]
    for r, e in zip(result, expected):
        assert r == approx(e)

    result = my_array.scalar_multiply(10, result)
    assert len(result) == 10
    for r, e in zip(result, expected):
        assert r == approx(e*10)

    manager.shutdown(connection=cxn)
