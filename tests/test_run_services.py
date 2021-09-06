import time
import threading

import conftest

import pytest

from msl.network import connect, Service, MSLNetworkError, LinkedClient
from msl.examples.network import Echo
from msl.network.manager import run_services


def test_single_service():

    class ShutdownableEcho(Echo):
        def shutdown_service(self, *args, **kwargs):
            pass

    port = conftest.Manager.get_available_port()

    run_thread = threading.Thread(
        target=run_services,
        args=(ShutdownableEcho(),),
        kwargs={'port': port, 'log_file': conftest.Manager.log_file}
    )
    run_thread.start()

    # wait for the Manager to be running
    conftest.Manager.wait_start(port, 'Cannot connect to manager')

    # the LinkedClient waits for the Service to be running in LinkedClient.__init__
    link = LinkedClient('ShutdownableEcho', port=port, name='foobar')

    args, kwargs = link.echo(1, 2, 3)
    assert len(args) == 3
    assert args[0] == 1
    assert args[1] == 2
    assert args[2] == 3
    assert len(kwargs) == 0

    args, kwargs = link.echo(x=4, y=5, z=6)
    assert len(args) == 0
    assert kwargs['x'] == 4
    assert kwargs['y'] == 5
    assert kwargs['z'] == 6

    args, kwargs = link.echo(1, 2, 3, x=4, y=5, z=6)
    assert len(args) == 3
    assert args[0] == 1
    assert args[1] == 2
    assert args[2] == 3
    assert kwargs['x'] == 4
    assert kwargs['y'] == 5
    assert kwargs['z'] == 6

    assert len(link.service_attributes) == 2
    assert 'echo' in link.service_attributes
    assert 'shutdown_service' in link.service_attributes
    assert link.name == 'foobar'

    with pytest.raises(MSLNetworkError):
        link.does_not_exist()

    link.shutdown_service()
    link.disconnect()

    # the `run_services` function will block the unittests forever if the
    # LinkedClient did not shutdown ShutdownableEcho
    run_thread.join()


def test_multiple_services():

    class ShutdownableService(Service):
        def shutdown_service(self, *args, **kwargs):
            return args, kwargs

    class AddService(ShutdownableService):
        def add(self, a, b):
            return a + b

    class SubtractService(ShutdownableService):
        def subtract(self, a, b):
            return a - b

    password_manager = '<hey~you>'
    port = conftest.Manager.get_available_port()

    run_thread = threading.Thread(
        target=run_services,
        args=(AddService(), SubtractService()),
        kwargs={
            'password_manager': password_manager,
            'port': port,
            'log_file': conftest.Manager.log_file
        }
    )
    run_thread.start()

    # wait for the Manager to be running
    conftest.Manager.wait_start(port, 'Cannot connect to manager')

    cxn = connect(password_manager=password_manager, port=port)

    # wait for the Services to be running before linking
    while len(cxn.manager()['services']) != 2:
        time.sleep(0.1)

    s = cxn.link('SubtractService')
    a = cxn.link('AddService')
    assert a.add(1, 2) == 3
    assert s.subtract(1, 2) == -1

    # shut down the AddService
    reply = a.shutdown_service(1, x=9)
    assert reply == [[1], {'x': 9}]
    while len(cxn.manager()['services']) == 2:
        time.sleep(0.1)
    with pytest.raises(MSLNetworkError):
        a.add(1, 2)
    with pytest.raises(MSLNetworkError):
        cxn.link('AddService')

    # the SubtractService is still available
    assert s.subtract(9, 4) == 5
    # shut down the SubtractService
    reply = s.shutdown_service('foo', 'bar', xyz=None)
    assert reply == [['foo', 'bar'], {'xyz': None}]
    time.sleep(1)
    # ConnectionError because the Manager has shut down
    with pytest.raises(ConnectionError):
        s.subtract(1, 2)

    # the `run_services` function will block the unittests forever if the
    # Client did not shutdown both Services
    run_thread.join()
