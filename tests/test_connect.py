import os
import tempfile

import helper  # located in the tests folder

import pytest

from msl.network import connect, cryptography, MSLNetworkError


def test_wrong_port():
    manager = helper.ServiceStarter()

    with pytest.raises(MSLNetworkError) as e:
        connect(port=manager.get_available_port())
    assert e.match('[refused|failed]')

    manager.shutdown()


def test_wrong_certificate():
    manager = helper.ServiceStarter()

    # connecting with the wrong certificate fails
    path = os.path.join(tempfile.gettempdir(), 'msl-network-wrong-certificate.crt')
    cryptography.generate_certificate(path=path)
    kwargs = manager.kwargs.copy()
    kwargs['certfile'] = path
    with pytest.raises(MSLNetworkError) as e:
        connect(**kwargs, timeout=5)
    assert e.match('CERTIFICATE_VERIFY_FAILED')
    os.remove(path)

    manager.shutdown()


def test_tls_enabled():
    manager = helper.ServiceStarter(disable_tls=False)

    # connecting with TLS disabled fails
    kwargs = manager.kwargs.copy()
    kwargs['disable_tls'] = True
    with pytest.raises(TimeoutError) as e:
        connect(**kwargs, timeout=5)
    assert e.match('You have TLS disabled')

    manager.shutdown()


def test_tls_disabled():
    manager = helper.ServiceStarter(disable_tls=True)

    # connecting with TLS enabled fails
    kwargs = manager.kwargs.copy()
    kwargs['disable_tls'] = False
    with pytest.raises(MSLNetworkError) as e:
        connect(**kwargs, timeout=5)
    assert e.match('disable_tls=True')

    manager.shutdown()


def test_invalid_manager_password():
    manager = helper.ServiceStarter(password_manager='asdvgbaw4bn')

    # connecting with the wrong Manager password fails
    kwargs = manager.kwargs.copy()
    kwargs['password_manager'] = 'xxxxxxxxxxxxxxxx'
    with pytest.raises(MSLNetworkError) as e:
        connect(**kwargs, timeout=5)
    assert e.match('Wrong Manager password')

    manager.shutdown()


def test_valid_hostname():
    manager = helper.ServiceStarter(auth_hostname=True)
    cxn = connect(**manager.kwargs)
    manager.shutdown(cxn)


def test_invalid_login():
    manager = helper.ServiceStarter()

    # connecting with an invalid username fails
    kwargs = manager.kwargs.copy()
    kwargs['username'] = 'xxxxxxxxxxxxx'
    with pytest.raises(MSLNetworkError) as e:
        connect(**kwargs, timeout=5)
    assert e.match('Unregistered username')

    # connecting with a valid username but the wrong password fails
    kwargs = manager.kwargs.copy()
    kwargs['password'] = 'xxxxxxxxxxxxx'
    with pytest.raises(MSLNetworkError) as e:
        connect(**kwargs, timeout=5)
    assert e.match('Wrong login password')

    manager.shutdown()
