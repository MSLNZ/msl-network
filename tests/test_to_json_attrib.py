import threading

import pytest

import conftest
from msl.network import LinkedClient
from msl.network import Service
from msl.network import run_services


def test_to_json_attrib():
    class Complex:
        """Does not implement a `to_json()` method.

        This object cannot be returned as a result.
        """

        def __init__(self, z):
            self.z = complex(z)

    class ComplexSerializable:
        """Does implement a `to_json()` method.

        This object can be returned as a result.
        """

        def __init__(self, z):
            self.z = complex(z)

        def to_json(self):
            return {
                'real': self.z.real,
                'imag': self.z.imag,
            }

    class ComplexService(Service):

        def raw(self):
            return 1-1j

        def no_to_json_attrib(self):
            return Complex(1-1j)

        def has_to_json_attrib(self):
            return ComplexSerializable(1-1j)

        def shutdown_service(self):
            pass

    port = conftest.Manager.get_available_port()

    run_thread = threading.Thread(
        target=run_services,
        args=(ComplexService(),),
        kwargs={'port': port, 'log_file': conftest.Manager.log_file}
    )
    run_thread.start()

    # wait for the Manager to be running
    conftest.Manager.wait_start(port, 'Cannot connect to manager')

    # the LinkedClient waits for the Service to be running in LinkedClient.__init__
    link = LinkedClient('ComplexService', port=port)

    with pytest.raises(RuntimeError, match='is not JSON serializable'):
        link.raw()

    with pytest.raises(RuntimeError, match='is not JSON serializable'):
        link.no_to_json_attrib()

    assert link.has_to_json_attrib() == {'real': 1.0, 'imag': -1.0}

    link.shutdown_service()
    link.disconnect()

    # the `run_services` function will block the unittests forever if the
    # LinkedClient did not properly shut down ComplexService
    run_thread.join()
