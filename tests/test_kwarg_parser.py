from msl.network.service import parse_service_start_kwargs
from msl.network.manager import parse_run_forever_kwargs


def test_parse_service_start_kwargs():
    kwargs = {
        'host': 'a',
        'port': 'b',
        'timeout': 'c',
        'username': 'd',
        'password': 'e',
        'certfile': 'f',
        'disable_tls': 'g',
        'assert_hostname': 'h',
        'debug': 'i',
        # the --auth-password for the run_forever() is passed in
        # so the `password_manager` key should be created
        'auth_password': 'j',
        'foo': 'bar',  # ignored
    }
    k = parse_service_start_kwargs(**kwargs)
    assert len(k) == 10
    assert k['host'] == 'a'
    assert k['port'] == 'b'
    assert k['timeout'] == 'c'
    assert k['username'] == 'd'
    assert k['password'] == 'e'
    assert k['certfile'] == 'f'
    assert k['disable_tls'] == 'g'
    assert k['assert_hostname'] == 'h'
    assert k['debug'] == 'i'
    assert k['password_manager'] == 'j'
    assert 'foo' not in k


def test_parse_run_forever_kwargs():
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
        'certfile': 'h',
        'keyfile': 'i',
        'keyfile_password': 'j',
        'logfile': 'k',
        'foo': 'bar',  # ignored
    }
    k = parse_run_forever_kwargs(**kwargs)
    assert len(k) == 11
    assert k['port'] == 'a'
    assert k['auth_hostname'] == 'b'
    assert k['auth_login'] == 'c'
    assert k['auth_password'] == 'd'
    assert k['database'] == 'e'
    assert k['debug'] == 'f'
    assert k['disable_tls'] == 'g'
    assert k['certfile'] == 'h'
    assert k['keyfile'] == 'i'
    assert k['keyfile_password'] == 'j'
    assert k['logfile'] == 'k'
    assert 'foo' not in k
