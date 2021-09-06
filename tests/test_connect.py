import os
import tempfile
from time import perf_counter

import conftest

import pytest

from msl.network import (
    connect,
    cryptography,
    constants,
    MSLNetworkError,
)
from msl.network.utils import localhost_aliases


def test_no_manager_no_certificate_localhost():
    conftest.Manager.remove_files()
    match = r'Make sure a Network Manager is running on this computer$'
    with pytest.raises(ConnectionError, match=match):
        connect(disable_tls=False)


def test_no_manager_no_certificate_remotehost():
    conftest.Manager.remove_files()
    host = 'MSLNZ12345'
    match = r'Cannot connect to {}:{} to get the certificate$'.format(
        host, constants.PORT)
    with pytest.raises(ConnectionError, match=match):
        connect(host=host, disable_tls=False)


def test_no_manager_timeout_asyncio():
    timeout = 0.5
    match = r'Cannot connect to {}:{} within {} seconds$'.format(
        constants.HOSTNAME, constants.PORT, timeout)
    t0 = perf_counter()
    with pytest.raises(TimeoutError, match=match):
        connect(disable_tls=True, timeout=timeout)
    assert abs(timeout - (perf_counter() - t0)) < 0.2


def test_no_manager_no_timeout_localhost():
    match = r'Cannot connect to {}:{}$'.format(constants.HOSTNAME, constants.PORT)
    with pytest.raises(ConnectionError, match=match):
        connect(disable_tls=True, timeout=None)


def test_no_manager_no_timeout_remotehost():
    host = 'MSLNZ12345'
    match = r'Cannot connect to {}:{}$'.format(host, constants.PORT)
    with pytest.raises(ConnectionError, match=match):
        connect(host=host, disable_tls=True, timeout=None)


def test_no_certificate_tls_disabled():
    manager = conftest.Manager(disable_tls=True)
    os.remove(manager.cert_file)
    assert not os.path.isfile(manager.cert_file)
    kwargs = manager.kwargs.copy()
    kwargs['disable_tls'] = False
    kwargs['cert_file'] = None
    with pytest.raises(ConnectionError, match=r'Try setting disable_tls=True$'):
        connect(**kwargs)
    manager.shutdown()


def test_no_certificate():
    # calling connect() will automatically get the certificate from the server
    manager = conftest.Manager(disable_tls=False)
    cert_file = os.path.join(constants.CERT_DIR, constants.HOSTNAME + '.crt')
    assert manager.cert_file == cert_file
    os.remove(manager.cert_file)
    assert not os.path.isfile(manager.cert_file)
    assert not os.path.isfile(cert_file)
    kwargs = manager.kwargs.copy()
    kwargs['cert_file'] = None
    kwargs['auto_save'] = True
    cxn = connect(**kwargs)
    assert os.path.isfile(cert_file)
    os.remove(cert_file)
    manager.shutdown(connection=cxn)


def test_wrong_port():
    manager = conftest.Manager()
    kwargs = manager.kwargs.copy()
    kwargs['port'] = manager.get_available_port()
    match = r'Cannot connect to {}:{}$'.format(constants.HOSTNAME, kwargs['port'])
    with pytest.raises(ConnectionError, match=match):
        connect(timeout=100, **kwargs)
    manager.shutdown()


def test_wrong_certificate():
    manager = conftest.Manager()
    key = os.path.join(tempfile.gettempdir(), '.msl', 'wrong-certificate.key')
    cert = os.path.join(tempfile.gettempdir(), '.msl', 'wrong-certificate.crt')
    assert cryptography.generate_key(path=key) == key
    assert cryptography.generate_certificate(path=cert, key_path=key) == cert
    kwargs = manager.kwargs.copy()
    kwargs['cert_file'] = cert
    with pytest.raises(ConnectionError) as e:
        connect(**kwargs)
    msg = str(e.value)
    assert 'Perhaps the Network Manager is using a new certificate' in msg
    assert '{}:{}'.format(constants.HOSTNAME, kwargs['port']) in msg
    assert 'wrong-certificate.crt' in msg
    os.remove(key)
    os.remove(cert)
    manager.shutdown()


def test_tls_disabled():
    manager = conftest.Manager(disable_tls=False)
    kwargs = manager.kwargs.copy()
    kwargs['disable_tls'] = True
    with pytest.raises(ConnectionError, match=r'You have TLS disabled'):
        connect(**kwargs, timeout=5)
    manager.shutdown()


def test_tls_enabled():
    manager = conftest.Manager(disable_tls=True)
    kwargs = manager.kwargs.copy()
    kwargs['disable_tls'] = False
    with pytest.raises(ConnectionError, match=r'Try setting disable_tls=True$'):
        connect(**kwargs)
    manager.shutdown()


@pytest.mark.parametrize('host', localhost_aliases())
def test_hostname_mismatch(host):
    a = cryptography.x509.NameAttribute
    o = cryptography.x509.NameOID
    name = cryptography.x509.Name([a(o.COMMON_NAME, 'MSLNZ12345')])
    manager = conftest.Manager(cert_common_name=name)
    kwargs = manager.kwargs.copy()
    kwargs['host'] = host
    with pytest.raises(ConnectionError, match=r'set assert_hostname=False'):
        connect(assert_hostname=True, **kwargs)
    cxn = connect(assert_hostname=False, **kwargs)
    manager.shutdown(connection=cxn)


def test_invalid_manager_password():
    manager = conftest.Manager(password_manager='asdvgbaw4bn')
    kwargs = manager.kwargs.copy()
    kwargs['password_manager'] = 'x'
    with pytest.raises(MSLNetworkError, match=r'Wrong Manager password'):
        connect(**kwargs)
    manager.shutdown()


def test_invalid_username():
    manager = conftest.Manager()
    kwargs = manager.kwargs.copy()
    kwargs['username'] = 'x'
    with pytest.raises(MSLNetworkError, match=r'Unregistered username'):
        connect(**kwargs)
    manager.shutdown()


def test_invalid_password():
    manager = conftest.Manager()
    kwargs = manager.kwargs.copy()
    kwargs['password'] = 'x'
    with pytest.raises(MSLNetworkError, match=r'Wrong login password'):
        connect(**kwargs)
    manager.shutdown()
