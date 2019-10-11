import time
import threading
from socket import socket

import pytest

from msl.network import connect, Service, MSLNetworkError
from msl.network.manager import run_services


def test_run_servers():

    with socket() as sock:
        sock.bind(('', 0))  # get any available port
        port = sock.getsockname()[1]

    password_manager = '<hey~you>'

    class ShutdownableService(Service):

        def shutdown_service(self):
            self._shutdown()

    class AddService(ShutdownableService):

        def add(self, a, b):
            return a + b

    class SubtractService(ShutdownableService):

        def subtract(self, a, b):
            return a - b

    def run_client():
        time.sleep(1)  # wait for the Services to be running on the Manager
        cxn = connect(password_manager=password_manager, port=port)
        a = cxn.link('AddService')
        s = cxn.link('SubtractService')
        assert a.add(1, 2) == 3
        assert s.subtract(1, 2) == -1
        a.shutdown_service()
        s.shutdown_service()
        time.sleep(1)  # wait for the Manager to shut down
        with pytest.raises(MSLNetworkError):
            a.add(1, 2)
        with pytest.raises(MSLNetworkError):
            s.subtract(1, 2)

    client_thread = threading.Thread(target=run_client)
    client_thread.start()

    # the `run_services` function will block the unittests forever if the
    # Client did not shutdown both Services
    run_services(AddService(), SubtractService(), password_manager=password_manager, port=port)

    client_thread.join()
