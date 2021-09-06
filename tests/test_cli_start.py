import os
import sys
import tempfile

import conftest

from msl.network import cli
from msl.network.database import UsersTable

db = os.path.join(tempfile.gettempdir(), 'test_cli_start.db')
out = os.path.join(tempfile.gettempdir(), 'test_cli_start.tmp')
for item in [db, out]:
    if os.path.isfile(item):
        os.remove(item)

table = UsersTable(database=db)


def teardown_module(module):
    table.close()
    os.remove(db)
    os.remove(out)


def get_args(command):
    parser = cli.configure_parser()
    return parser.parse_args(command.split())


def test_cannot_use_multiple_auth_methods():
    flags = [
        '--auth-hostname --auth-password hello',
        '--auth-hostname --auth-login',
        '--auth-login --auth-password hello world!',
    ]
    for flag in flags:
        sys.stdout = open(out, 'w')
        args = get_args('start ' + flag + ' --logfile ' + helper.ServiceStarter.logfile)
        args.func(args)
        sys.stdout.close()
        lines = [line.strip() for line in open(out, 'r').readlines()]
        assert lines[-1].endswith('ValueError: Cannot specify multiple authentication methods')


def test_invalid_port():
    sys.stdout = open(out, 'w')
    args = get_args('start --port 1234x --logfile ' + helper.ServiceStarter.logfile)
    args.func(args)
    sys.stdout.close()
    lines = [line.strip() for line in open(out, 'r').readlines()]
    assert lines[-1].endswith('ValueError: The port number must be an integer')


def test_cannot_use_auth_login_with_empty_table():
    sys.stdout = open(out, 'w')
    args = get_args('start --auth-login --database ' + db + ' --logfile ' + helper.ServiceStarter.logfile)
    args.func(args)
    sys.stdout.close()
    lines = [line.strip() for line in open(out, 'r').readlines()]
    assert lines[-2].endswith('ValueError: The Users table is empty. No one could log in.')
