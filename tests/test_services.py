import concurrent.futures
import math
import time

from pytest import approx
from pytest import raises

import conftest
from msl.examples.network import BasicMath
from msl.examples.network import Echo
from msl.examples.network import MyArray
from msl.network import Service
from msl.network import connect


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
    assert isinstance(add, concurrent.futures.Future)
    assert bm.subtract(1, 1) == 0
    assert add.result() == 2

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
    with raises(RuntimeError):
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
    assert euler.result() == approx(math.exp(1))
    assert pi.result() == approx(math.pi)
    assert add.result() == approx(451.57 - 745.12)
    assert subtract.result() == approx(-99.82 + 872.45)
    assert multiply.result() == approx(-53.33 * 54.44)
    assert divide.result() == approx(4.2 / 19.3)
    assert err.result()
    assert power.result() == approx(123.45 ** 3)
    assert time.perf_counter() - t0 < maximum_dt

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

    assert power.result() == approx(math.pi ** math.exp(1))
    assert len(linspace.result()) == 1e6

    manager.shutdown(connection=cxn1)


def test_private_retrieval():
    manager = conftest.Manager(BasicMath)

    cxn = connect(**manager.kwargs)
    bm = cxn.link('BasicMath')

    with raises(RuntimeError, match=r'Cannot request a private attribute'):
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
    with raises(concurrent.futures.TimeoutError):
        bm.power(a, b, timeout=3)

    manager.shutdown()


def test_basic_math_timeout_asynchronous():
    manager = conftest.Manager(BasicMath)
    cxn = connect(**manager.kwargs)
    bm = cxn.link('BasicMath')

    a, b = 2, 10

    add_1 = bm.add(a, b, asynchronous=True)
    power_1 = bm.power(a, b, asynchronous=True)
    assert add_1.result(timeout=10) == a+b
    assert power_1.result(timeout=10) == a**b

    # # the `add` method sleeps for 1 second -> no timeout expected
    # # the `power` method sleeps for 6 seconds -> timeout expected
    add_2 = bm.add(a, b, asynchronous=True)
    power_2 = bm.power(a, b, asynchronous=True)
    assert add_2.result(timeout=3) == a+b
    with raises(concurrent.futures.TimeoutError):
        assert power_2.result(timeout=0.5) == a**b

    manager.shutdown()


def test_json_not_serializable_synchronous():
    class Complex(Service):
        def integer(self):
            return 1
        def complex(self):
            return 1 + 2j

    manager = conftest.Manager(Complex)
    cxn = connect(**manager.kwargs)

    c = cxn.link('Complex')
    assert c.integer() == 1

    with raises(RuntimeError, match=r'not JSON serializable'):
        c.complex()

    assert c.integer() == 1

    manager.shutdown(connection=cxn)


def test_json_not_serializable_asynchronous():
    class Complex(Service):
        def integer(self):
            return 1
        def complex(self):
            return 1 + 2j

    manager = conftest.Manager(Complex)
    cxn = connect(**manager.kwargs)

    c = cxn.link('Complex')

    future = c.integer(asynchronous=True)
    assert future.result() == 1

    future = c.complex(asynchronous=True)
    with raises(RuntimeError, match=r'not JSON serializable'):
        future.result()

    future = c.integer(asynchronous=True)
    assert future.result() == 1

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
    for i in range(30):  # pretend that 30 == infinity (limit for macOS seems to be about 40)
        spawns.append(cxn.spawn('Client%d' % i))
        links.append(spawns[-1].link('Echo'))
        assert links[-1].echo(i)[0][0] == i
    assert len(cxn.identities()['clients']) == len(spawns) + 1
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
    with raises(RuntimeError, match=r'PermissionError: The maximum number of Clients'):
        client2.link('Echo')
    with raises(RuntimeError, match=r'PermissionError: The maximum number of Clients'):
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
    with raises(RuntimeError, match=r'PermissionError: The maximum number of Clients'):
        client6.link('Echo')
    assert len(cxn.identities()['clients']) == len(spawns) + 2
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
    manager = conftest.Manager(MyArray, ignore_attributes='linspace')
    cxn = connect(**manager.kwargs)

    # 'linspace' is not a publicly known attribute
    identity = cxn.identities()['services']['MyArray']
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


def test_stream_reader_limit():
    manager = conftest.Manager(Echo, read_limit=1024)
    cxn = connect(**manager.kwargs)

    echo = cxn.link('Echo')

    assert echo.echo(1) == [[1], {}]

    with raises(concurrent.futures.TimeoutError):
        echo.echo('x' * 1024, timeout=5)

    # the Service must still be running
    assert echo.echo(z='z' * 512) == [[], {'z': 'z' * 512}]

    manager.shutdown(connection=cxn)
