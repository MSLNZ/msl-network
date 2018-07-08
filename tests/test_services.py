import time
import math
import asyncio

from pytest import approx, raises

import helper  # located in the tests folder

from msl.network import connect
from msl.network.exceptions import MSLNetworkError
from msl.examples.network.basic_math import BasicMath
from msl.examples.network.array import Array
from msl.examples.network.echo import Echo


def test_echo():
    services = helper.ServiceStarter((Echo,))

    cxn = connect(**services.kwargs)

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

    services.shutdown(cxn)


def test_asynchronous_synchronous_simultaneous():
    services = helper.ServiceStarter((BasicMath,))

    cxn = connect(**services.kwargs)

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

    services.shutdown(cxn)


def test_basic_math_synchronous():
    services = helper.ServiceStarter((BasicMath,))

    cxn = connect(**services.kwargs)

    assert cxn.send_request('BasicMath', 'euler') == approx(math.exp(1))
    assert cxn.send_request('BasicMath', 'pi') == approx(math.pi)
    assert cxn.send_request('BasicMath', 'add', -4, 10) == -4 + 10

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

    services.shutdown(cxn)


def test_basic_math_asynchronous():
    services = helper.ServiceStarter((BasicMath,))

    cxn = connect(**services.kwargs)
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

    services.shutdown(cxn)


def test_array_synchronous():
    services = helper.ServiceStarter((Array,))

    cxn = connect(**services.kwargs)

    array = cxn.link('Array')
    out1 = array.linspace(-1, 1, 100)
    assert len(out1) == 100
    assert out1[0] == approx(-1)
    assert out1[-1] == approx(1)

    out2 = array.scalar_multiply(-2, out1)
    assert len(out2) == 100
    assert out2[0] == approx(2)
    assert out2[-1] == approx(-2)

    services.shutdown(cxn)


def test_basic_math_and_array_asynchronous():

    services = helper.ServiceStarter((BasicMath, Array,))

    cxn = connect(**services.kwargs)

    bm = cxn.link('BasicMath')
    array = cxn.link('Array')

    power = bm.power(math.pi, math.exp(1), asynchronous=True)
    linspace = array.linspace(0, 1, 1e6, asynchronous=True)

    cxn.send_pending_requests()

    assert power.result() == approx(math.pi ** math.exp(1))
    assert len(linspace.result()) == 1e6

    services.shutdown(cxn)


def test_spawn_basic_math_and_array_asynchronous():

    services = helper.ServiceStarter((BasicMath, Array,))

    cxn1 = connect(**services.kwargs)
    cxn2 = cxn1.spawn()

    bm = cxn1.link('BasicMath')
    array = cxn2.link('Array')

    power = bm.power(math.pi, math.exp(1), asynchronous=True)
    linspace = array.linspace(0, 1, 1e6, asynchronous=True)

    cxn1.send_pending_requests()
    cxn2.send_pending_requests()

    assert power.result() == approx(math.pi ** math.exp(1))
    assert len(linspace.result()) == 1e6

    assert cxn2.address_manager is not None
    assert cxn2.port is not None

    services.shutdown(cxn1)

    # shutting down the manager using cxn1 will also disconnect cxn2
    assert cxn2.address_manager is None
    assert cxn2.port is None


def test_password_retrieval():
    services = helper.ServiceStarter((BasicMath,))

    cxn = connect(**services.kwargs)
    bm = cxn.link('BasicMath')

    assert bm.password('any name') != services.admin_password
    assert bm._password() != services.admin_password

    services.shutdown(cxn)
