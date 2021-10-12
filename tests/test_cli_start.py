import os

import pytest

import conftest

from msl.network import cli
from msl.network.database import UsersTable


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
