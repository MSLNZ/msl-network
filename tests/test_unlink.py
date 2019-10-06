import time
import threading
from socket import socket

import helper  # located in the tests folder

import pytest

from msl.examples.network import Echo
from msl.network import connect, LinkedClient
from msl.network.exceptions import MSLNetworkError
from msl.network.manager import run_services


def test_unlink_client_max1():

    services = helper.ServiceStarter((Echo,), max_clients=1)

    cxn1 = connect(**services.kwargs)
    cxn2 = connect(**services.kwargs)

    link1 = cxn1.link('Echo')
    assert repr(link1).startswith("<Link with Echo[")
    assert link1.service_name == 'Echo'
    assert link1.echo(1, x=2) == [[1], {'x': 2}]

    # the same Client can re-link to the same Service
    link1b = cxn1.link('Echo')
    assert link1b is not link1
    assert link1b.service_name == 'Echo'
    assert link1b.echo(1, x=2) == [[1], {'x': 2}]

    # another Client cannot link
    with pytest.raises(MSLNetworkError) as err:
        cxn2.link('Echo')
    assert 'The maximum number of Clients are already linked' in str(err.value)

    link1.unlink()
    assert repr(link1).startswith("<Un-Linked from Echo[")
    assert link1._client is None
    with pytest.raises(AttributeError) as err:
        link1.echo(1)
    assert str(err.value).startswith("'NoneType' object has no attribute")

    # another Client can now link
    link2 = cxn2.link('Echo')
    assert link2.service_name == 'Echo'
    assert link2.echo(1, x=2) == [[1], {'x': 2}]

    link2.unlink()
    assert link2._client is None
    with pytest.raises(AttributeError) as err:
        link2.echo(1)
    assert str(err.value).startswith("'NoneType' object has no attribute")

    # un-linking multiple times is okay
    for i in range(20):
        link2.unlink()
        link2.disconnect()  # an alias for unlink

    services.shutdown(cxn1)

    # shutting down the manager using cxn1 will also disconnect cxn2
    assert cxn2.address_manager is None
    assert cxn2.port is None


def test_unlink_client_max10():

    services = helper.ServiceStarter((Echo,), max_clients=10)

    clients = [connect(**services.kwargs) for _ in range(10)]
    links = [client.link('Echo') for client in clients]
    for link in links:
        assert link.service_name == 'Echo'
        assert link.echo(1, x=2) == [[1], {'x': 2}]

    cxn = connect(**services.kwargs)

    # another Client cannot link
    with pytest.raises(MSLNetworkError) as err:
        cxn.link('Echo')
    assert 'The maximum number of Clients are already linked' in str(err.value)

    links[0].unlink()
    assert links[0]._client is None
    with pytest.raises(AttributeError) as err:
        links[0].echo(1)
    assert str(err.value).startswith("'NoneType' object has no attribute")

    # another Client can now link
    link2 = cxn.link('Echo')
    assert link2.service_name == 'Echo'
    assert link2.echo(1, x=2) == [[1], {'x': 2}]

    link2.unlink()
    assert link2._client is None
    with pytest.raises(AttributeError) as err:
        link2.echo(1)
    assert str(err.value).startswith("'NoneType' object has no attribute")

    services.shutdown(cxn)

    # shutting down the manager using cxn will also disconnect all clients
    for client in clients:
        assert client.address_manager is None
        assert client.port is None


def test_unlink_linkedclient_max10():

    with socket() as sock:
        sock.bind(('', 0))  # get any available port
        port = sock.getsockname()[1]

    class DisconnectableEcho(Echo):

        def __init__(self):
            super(DisconnectableEcho, self).__init__(max_clients=10)

        def disconnect_service(self):
            self._disconnect()

    def run_client():
        time.sleep(1)  # allow for the Manager and Service to start
        linked_clients = [LinkedClient('DisconnectableEcho', port=port, name='foobar%d' % i) for i in range(10)]

        for i, link in enumerate(linked_clients):
            assert link.service_name == 'DisconnectableEcho'
            assert link.name == 'foobar%d' % i
            assert link.echo(1, x=2) == [[1], {'x': 2}]

        # creating another LinkedClient is not allowed
        with pytest.raises(MSLNetworkError) as err:
            LinkedClient('DisconnectableEcho', port=port, name='foobar10')
        assert 'The maximum number of Clients are already linked' in str(err.value)

        linked_clients[0].unlink()
        assert linked_clients[0]._link is None
        with pytest.raises(AttributeError) as err:
            linked_clients[0].echo(1)
        assert str(err.value).startswith("'NoneType' object has no attribute")

        # another LinkedClient can now be created
        link2 = LinkedClient('DisconnectableEcho', port=port, name='foobar10')
        assert link2.service_name == 'DisconnectableEcho'
        assert link2.name == 'foobar10'
        assert link2.echo(1, x=2) == [[1], {'x': 2}]
        assert repr(link2).startswith('<Link[name=foobar10]')
        link2.unlink()
        assert link2._link is None
        assert repr(link2).startswith('<Un-Linked[name=foobar10]')
        with pytest.raises(AttributeError) as err:
            link2.echo(1)
        assert str(err.value).startswith("'NoneType' object has no attribute")

        # un-linking the LinkedClient multiple times is okay
        for i in range(20):
            link2.unlink()
        link2.disconnect()  # a linkedClient can disconnect the Client via self._client

        # shutdown the DisconnectableEcho Service and disconnect the LinkedClient
        # from the Manager, the second item in the LinkedClient list is still linked
        # and can therefore still send requests
        assert linked_clients[1].service_name == 'DisconnectableEcho'
        assert linked_clients[1].name == 'foobar1'
        assert linked_clients[1].echo(1, x=2) == [[1], {'x': 2}]
        linked_clients[1].disconnect_service()
        linked_clients[1].unlink()
        linked_clients[1].disconnect()

        # this LinkedClient was already unlinked but calling disconnect should not raise an error
        linked_clients[0].disconnect()

        # once the DisconnectableEcho shuts down the Manager also automatically shuts down
        # since the DisconnectableEcho was started using the run_services() function
        for client in linked_clients[2:]:
            # can either raise MSLNetworkError (if the Manager is still running)
            # or ConnectionError (if the Manager has also shut down)
            with pytest.raises((MSLNetworkError, ConnectionError)):
                client.unlink()
            client.disconnect()  # can still disconnect
            client.disconnect()  # even multiple times
            client.disconnect()
            client.disconnect()
            client.disconnect()

    client_thread = threading.Thread(target=run_client)
    client_thread.start()

    # the `run_services` function will block the unittests forever if a
    # LinkedClient does not shutdown DisconnectableEcho
    run_services(DisconnectableEcho(), port=port)

    client_thread.join()
