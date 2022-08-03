import os

import pytest

import conftest

from msl.network import cli
from msl.network.database import UsersTable
from msl.network.constants import (
    HOSTNAME,
    IPV4_ADDRESSES,
    NETWORK_MANAGER_RUNNING_PREFIX,
    CERT_DIR,
    KEY_DIR,
)


def process(command):
    parser = cli.configure_parser()
    args = parser.parse_args(command.split())
    args.func(args)


@pytest.mark.parametrize(
    'flag',
    ['--auth-hostname --auth-password hello',
     '--auth-hostname --auth-login',
     '--auth-login --auth-password h e l l o']
)
def test_multiple_auth_methods(flag, capsys):
    process('start ' + flag)
    _, err = capsys.readouterr()
    assert err.rstrip().endswith('Cannot specify multiple authentication methods')


@pytest.mark.parametrize('port', [-1, '1234x'])
def test_invalid_port(port, capsys):
    process('start --port {}'.format(port))
    _, err = capsys.readouterr()
    assert err.rstrip().endswith('ValueError: The port must be a positive integer')


def test_cannot_use_auth_login_with_empty_table(capsys):
    db = conftest.Manager.database
    try:
        os.remove(db)
    except OSError:
        pass

    table = UsersTable(database=db)
    process('start --auth-login --database ' + db)
    table.close()
    out, err = capsys.readouterr()
    out_lines = out.splitlines()
    err_lines = err.splitlines()
    for i in [1, 2, 3]:
        assert db in os.path.normpath(out_lines[i])
    assert len(err_lines) == 2
    assert err_lines[0] == 'The \'auth_users\' table is empty, no one could log in'
    os.remove(db)


def test_invalid_log_level(capsys):
    process('start --log-level INVALID')
    _, err = capsys.readouterr()
    assert err.rstrip().endswith("ValueError: Cannot set logging level to 'INVALID'")


@pytest.mark.parametrize('host', [None, HOSTNAME, 'localhost', '127.0.0.1', *IPV4_ADDRESSES])
def test_host(host):
    filename = host or 'localhost'
    cert_file = os.path.join(CERT_DIR, f'{filename}.crt')
    key_file = os.path.join(KEY_DIR, f'{filename}.key')

    if os.path.isfile(cert_file):
        os.remove(cert_file)
    if os.path.isfile(key_file):
        os.remove(key_file)

    manager = conftest.Manager(host=host)
    with open(manager.log_file, mode='rt') as fp:
        lines = [line.rstrip() for line in fp.readlines()]

    assert os.path.isfile(cert_file)
    assert os.path.isfile(key_file)

    manager.kwargs['cert_file'] = cert_file
    manager.shutdown()

    if host is None or host == 'localhost':
        # the manager.shutdown() automatically deleted the files
        assert not os.path.isfile(cert_file)
        assert not os.path.isfile(key_file)
    else:
        os.remove(cert_file)
        os.remove(key_file)

    _host = host or HOSTNAME
    text = f'{NETWORK_MANAGER_RUNNING_PREFIX} {_host}:{manager.port} (TLS ENABLED)'
    assert lines[0].endswith(cert_file)
    assert lines[-1].endswith(text)
