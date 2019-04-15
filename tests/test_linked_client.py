import time
import threading
from socket import socket

import pytest

from msl.network import LinkedClient, MSLNetworkError
from msl.examples.network import Echo
from msl.network.manager import run_services


def test_linked_echo():
    with socket() as sock:
        sock.bind(('', 0))  # get any available port
        port = sock.getsockname()[1]

    class DisconnectableEcho(Echo):
        def disconnect_service(self):
            self._disconnect()

    def run_client():
        time.sleep(1)  # wait for the Services to be running on the Manager
        link = LinkedClient('DisconnectableEcho', port=port, name='foobar')

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
        assert 'disconnect_service' in link.service_attributes
        assert link.name == 'foobar'

        with pytest.raises(MSLNetworkError):
            link.does_not_exist()

        link.disconnect_service()
        link.disconnect()

    client_thread = threading.Thread(target=run_client)
    client_thread.start()

    # the `run_services` function will block the unittests forever if the
    # LinkedClient did not shutdown DisconnectableEcho
    run_services(DisconnectableEcho(), port=port)

    client_thread.join()
