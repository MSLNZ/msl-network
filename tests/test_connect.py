import os
import time
import tempfile
from socket import socket
from threading import Thread

import pytest

from msl.network import connect, cli_start, cryptography, UsersTable, MSLNetworkError


def get_available_port():
    with socket() as sock:
        sock.bind(('', 0))  # get any available port
        return sock.getsockname()[1]


class Manager(object):

    def __init__(self, sleep=1.0):
        # create the default command-line arguments that are used to start a Manager
        self.auth_hostname = False
        self.auth_login = False
        self.auth_password = None
        self.cert = None
        self.database = tempfile.gettempdir() + '/msl-network-testing.db'
        self.debug = False
        self.disable_tls = False
        self.key = None
        self.key_password = None
        self.port = get_available_port()

        self._sleep = sleep

        # need a UsersTable with an administrator to be able to shutdown the Manager
        ut = UsersTable(database=self.database)
        self.admin_username, self.admin_password = 'admin', 'whatever'
        ut.insert(self.admin_username, self.admin_password, True)
        ut.close()

    def start(self):
        self._manager_thread = Thread(target=cli_start.execute, args=(self,), daemon=True)
        self._manager_thread.start()
        time.sleep(self._sleep)

    def shutdown(self, **kwargs):
        cxn = connect(port=self.port, username=self.admin_username, password=self.admin_password, **kwargs)
        cxn.admin_request('shutdown_manager')
        cxn.disconnect()
        self._manager_thread.join()
        os.remove(self.database)


def test_default_settings():

    mgr = Manager()

    # start the Network Manager with the default settings
    mgr.start()

    # test that connecting to the wrong port fails
    with pytest.raises(MSLNetworkError):
        connect(port=get_available_port())

    # test that connecting with the wrong certificate fails
    path = tempfile.gettempdir() + '/msl-network-wrong-certificate.crt'
    cryptography.generate_certificate(path=path)
    with pytest.raises(MSLNetworkError) as e:
        connect(port=mgr.port, certificate=path)
    os.remove(path)
    assert 'CERTIFICATE_VERIFY_FAILED' in str(e.value)

    # test that connecting with TLS disabled fails
    with pytest.raises(TimeoutError):
        connect(port=mgr.port, disable_tls=True, timeout=2.0)

    # shutdown the Manager
    mgr.shutdown()


def test_tls_disabled():

    mgr = Manager()

    # start the Network Manager without TLS
    mgr.disable_tls = True
    mgr.start()

    # test that connecting with TLS enabled fails
    with pytest.raises(MSLNetworkError) as e:
        connect(port=mgr.port, disable_tls=False)
    assert 'disable_tls=True' in str(e.value)

    mgr.shutdown(disable_tls=True)


def test_invalid_manager_password():

    mgr = Manager()

    password = 'the correct password'
    # start the Network Manager requiring a valid password
    mgr.auth_password = [password]  # the CLI expects a list
    mgr.start()

    # test that connecting with the wrong Manager password fails
    with pytest.raises(MSLNetworkError) as e:
        connect(port=mgr.port, password_manager='xxxxxxxxxxxxxxxx')
    assert 'Wrong Manager password' in str(e.value)

    mgr.shutdown(password_manager=password)


def test_valid_hostname():
    # since we are using 'localhost' this test is a dummy test

    mgr = Manager()

    # start the Network Manager requiring a valid hostname
    mgr.auth_hostname = True
    mgr.start()

    # the shutdown method contains a connect() method which will use 'localhost' as the hostname
    mgr.shutdown()


def test_invalid_login():
    mgr = Manager()

    # start the Network Manager requiring a valid login
    mgr.auth_login = True
    mgr.start()

    # test that connecting with an invalid username fails
    with pytest.raises(MSLNetworkError) as e:
        connect(port=mgr.port, username='someone invalid', password='will fail before asking')
    assert 'Unregistered username' in str(e.value)

    # test that connecting with a valid username but the wrong password fails
    with pytest.raises(MSLNetworkError) as e:
        connect(port=mgr.port, username=mgr.admin_username, password='xxxxxxxxxxxxx')
    assert 'Wrong login password' in str(e.value)

    mgr.shutdown()
