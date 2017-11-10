import os
import sys
import tempfile

from msl.network import cli
from msl.network.database import UsersTable

db = os.path.join(tempfile.gettempdir(), 'test_cli_user.db')
out = os.path.join(tempfile.gettempdir(), 'test_cli_user.tmp')
pw_file = os.path.join(tempfile.gettempdir(), 'password.tmp')
table = UsersTable(db)


def get_args(command):
    parser = cli.configure_parser()
    return parser.parse_args(command.split())


def check_value_error(out, base, cmd, text):
    sys.stdout = open(out, 'w')
    args = get_args(base + cmd)
    args.func(args)
    sys.stdout.close()
    line = open(out, 'r').readline().strip()
    assert line.startswith('ValueError:') and text in line


def teardown_module(module):
    table.close()
    os.remove(db)
    os.remove(out)
    os.remove(pw_file)


def test_cli_user():

    users = [
        ('admin', 'the administrator', True),
        ('enforcer', 'the second in command', 1),
        ('Alice', 'alice123', False),
        ('Bob', 'bob likes cheese', []),
        ('charlie', 'CharliesAngels', 0),
        ('jdoe', 'anonymous & unknown', None),
    ]

    for user in users:
        table.insert(*user)

    base_command = f'user --database {db} '

    # action: list
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'list')
    args.func(args)
    sys.stdout.close()
    lines = [line.split() for line in open(out, 'r').readlines()]
    assert lines[0][0] == 'Users'
    assert lines[2][0] == 'Username'
    assert lines[3][0].startswith('=')
    assert ['enforcer', 'True'] in lines
    assert ['jdoe', 'False'] in lines

    # action: no username
    for item in ('insert', 'add', 'remove', 'delete', 'update'):
        check_value_error(out, base_command, item, 'username')

    # action: insert/add ... no password specified
    check_value_error(out, base_command, 'insert person', 'password')
    check_value_error(out, base_command, 'add person', 'password')

    # action insert
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'add person1 --password password123')
    args.func(args)
    sys.stdout.close()
    line = open(out, 'r').readline().strip()
    assert line.startswith('person1') and line.endswith('added')
    assert 'person1' in table.usernames()

    # action insert ... already exists
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'add person1 --password password123')
    args.func(args)
    sys.stdout.close()
    assert open(out, 'r').readline().startswith('ValueError:')

    # action remove
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'remove person1')
    args.func(args)
    sys.stdout.close()
    line = open(out, 'r').readline().strip()
    assert line.startswith('person1') and line.endswith('removed')
    assert 'person1' not in table.usernames()

    # action remove ... does not exist
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'add person2')
    args.func(args)
    sys.stdout.close()
    assert open(out, 'r').readline().startswith('ValueError:')

    # action update
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'update Alice --password password123 --admin')
    args.func(args)
    sys.stdout.close()
    line = open(out, 'r').readline().strip()
    assert line.startswith('Updated') and line.endswith('Alice')
    assert table.is_admin('Alice')

    # action update ... does not exist
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'update person3')
    args.func(args)
    sys.stdout.close()
    assert open(out, 'r').readline().startswith('ValueError:')

    # action update ... password from a file
    sys.stdout = open(out, 'w')
    password = 'a password in a file'
    with open(pw_file, 'w') as fp:
        fp.write(password)

    args = get_args(base_command + 'update Alice --password ' + pw_file)
    args.func(args)
    sys.stdout.close()
    line = open(out, 'r').readline().strip()
    assert line.startswith('Updated') and line.endswith('Alice')
    assert table.is_password_valid('Alice', password)
