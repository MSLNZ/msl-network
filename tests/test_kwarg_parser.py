from msl.network.service import filter_service_start_kwargs
from msl.network.manager import filter_run_forever_kwargs
from msl.network.client import filter_client_connect_kwargs


def test_filter_service_start_kwargs():
    kwargs = {
        'host': 'a',
        'port': 'b',
        'timeout': 'c',
        'username': 'd',
        'password': 'e',
        'cert_file': 'f',
        'disable_tls': 'g',
        'assert_hostname': 'h',
        'debug': 'i',
        # the --auth-password for the run_forever() is passed in
        # so the `password_manager` key should be created
        'auth_password': 'j',
        'foo': 'bar',  # ignored
        'name': 'buddy',
        'auto_save': True,
    }
    k = filter_service_start_kwargs(**kwargs)
    assert len(k) == 12
    assert k['name'] == 'buddy'
    assert k['host'] == 'a'
    assert k['port'] == 'b'
    assert k['timeout'] == 'c'
    assert k['username'] == 'd'
    assert k['password'] == 'e'
    assert k['cert_file'] == 'f'
    assert k['disable_tls'] == 'g'
    assert k['assert_hostname'] == 'h'
    assert k['debug'] == 'i'
    assert k['password_manager'] == 'j'
    assert 'foo' not in k
    assert k['auto_save'] is True


def test_filter_run_forever_kwargs():
    kwargs = {
        'port': 'a',
        'auth_hostname': 'b',
        'auth_login': 'c',
        # pretend the `password_manager` was passed in
        # so the `auth_password` key should be created
        'password_manager': 'd',
        'database': 'e',
        'debug': 'f',
        'disable_tls': 'g',
        'cert_file': 'h',
        'key_file': 'i',
        'key_file_password': 'j',
        'log_file': 'k',
        'foo': 'bar',  # ignored
        'auto_save': 'ignored',
    }
    k = filter_run_forever_kwargs(**kwargs)
    assert len(k) == 11
    assert k['port'] == 'a'
    assert k['auth_hostname'] == 'b'
    assert k['auth_login'] == 'c'
    assert k['auth_password'] == 'd'
    assert k['database'] == 'e'
    assert k['debug'] == 'f'
    assert k['disable_tls'] == 'g'
    assert k['cert_file'] == 'h'
    assert k['key_file'] == 'i'
    assert k['key_file_password'] == 'j'
    assert k['log_file'] == 'k'
    assert 'foo' not in k
    assert 'auto_save' not in k


def test_filter_client_connect_kwargs():
    kwargs = {
        'host': 'a',
        'port': 'b',
        'timeout': 'c',
        'username': 'd',
        'password': 'e',
        'cert_file': 'f',
        'disable_tls': 'g',
        'assert_hostname': 'h',
        'debug': 'i',
        'password_manager': 'j',
        'name': 'k',
        'foo': 'bar',  # ignored
        'new': 9,  # ignored
        'auto_save': False,
    }
    k = filter_client_connect_kwargs(**kwargs)
    assert len(k) == 12
    assert k['host'] == 'a'
    assert k['port'] == 'b'
    assert k['timeout'] == 'c'
    assert k['username'] == 'd'
    assert k['password'] == 'e'
    assert k['cert_file'] == 'f'
    assert k['disable_tls'] == 'g'
    assert k['assert_hostname'] == 'h'
    assert k['debug'] == 'i'
    assert k['password_manager'] == 'j'
    assert k['name'] == 'k'
    assert k['auto_save'] is False
    assert 'foo' not in k
    assert 'new' not in k
