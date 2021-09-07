import os
import tempfile

import pytest

import conftest

from msl.network import cli
from msl.network.database import UsersTable
from msl.network.constants import DATABASE


def process(command):
    parser = cli.configure_parser()
    args = parser.parse_args(command.split())
    args.func(args)


def remove_default():
    try:
        os.remove(DATABASE)
    except OSError:
        pass


def create_default():
    remove_default()
    users = [
        ('admin', 'the administrator', True),
        ('the-enforcer', 'the second in command', 1),
        ('Alice', 'alice123', False),
        ('Bob', 'bob likes cheese', []),
        ('charlie', 'CharliesAngels', 0),
        ('j.doe', 'anonymous & unknown', None),
    ]
    with UsersTable() as table:
        for user in users:
            table.insert(*user)


def test_path():
    conftest.Manager.remove_files()
    remove_default()

    assert DATABASE != conftest.Manager.database
    assert not os.path.isfile(DATABASE)
    assert not os.path.isfile(conftest.Manager.database)

    # need to specify an action, so use the "list" action
    process('user list')
    assert os.path.isfile(DATABASE)
    assert not os.path.isfile(conftest.Manager.database)
    os.remove(DATABASE)

    process('user list --database {}'.format(conftest.Manager.database))
    assert os.path.isfile(conftest.Manager.database)
    assert not os.path.isfile(DATABASE)
    os.remove(conftest.Manager.database)


@pytest.mark.parametrize('action', ['add', 'insert', 'remove', 'delete', 'update'])
def test_no_username(action, capsys):
    process('user ' + action)
    out, err = capsys.readouterr()
    assert out.rstrip() == 'ValueError: You must specify a username to {}'.format(action)
    assert not err


def test_list_none(capsys):
    remove_default()
    process('user list')
    out, err = capsys.readouterr()
    assert out.rstrip() == 'There are no users in the database'
    assert not err


def test_list(capsys):
    create_default()
    process('user list')
    out, err = capsys.readouterr()
    out_lines = out.splitlines()
    assert not err
    assert out_lines[0] == 'Users in {}'.format(DATABASE)
    assert not out_lines[1]
    assert out_lines[2] == 'Username     Administrator'
    assert out_lines[3] == '============ ============='
    assert out_lines[4] == 'Alice        False'
    assert out_lines[5] == 'Bob          False'
    assert out_lines[6] == 'admin        True'
    assert out_lines[7] == 'charlie      False'
    assert out_lines[8] == 'j.doe        False'
    assert out_lines[9] == 'the-enforcer True'


@pytest.mark.parametrize('action', ['add', 'insert'])
def test_add_no_password(action, capsys):
    process('user {} the.person'.format(action))
    out, err = capsys.readouterr()
    assert out.rstrip() == 'ValueError: You must specify a password for the.person'
    assert not err


@pytest.mark.parametrize('action', ['add', 'insert'])
def test_add(action, capsys):
    remove_default()
    process('user {} the.person --password pw'.format(action))
    out, err = capsys.readouterr()
    assert out.rstrip() == 'the.person has been {}ed'.format(action)
    assert not err


@pytest.mark.parametrize('action', ['add', 'insert'])
def test_add_already_exists(action, capsys):
    process('user {} the.person --password pw'.format(action))
    out, err = capsys.readouterr()
    assert out.rstrip() == "ValueError: A user with the name 'the.person' already exists"
    assert not err


@pytest.mark.parametrize('action', ['add', 'insert'])
def test_add_bad_username(action, capsys):
    process('user {} person:1234 --password pw'.format(action))
    out, err = capsys.readouterr()
    assert out.rstrip() == 'ValueError: A username cannot end with ":<integer>"'
    assert not err


@pytest.mark.parametrize('action', ['add', 'insert'])
def test_add_use_password_file(action, capsys):
    remove_default()
    pw_file = os.path.join(tempfile.gettempdir(), 'password.tmp')
    with open(pw_file, mode='wt') as fp:
        fp.write('a password in a file')

    process('user {} person --password {}'.format(action, pw_file))
    out, err = capsys.readouterr()
    assert not err
    assert out.splitlines() == [
        'Reading the password from the file',
        'person has been {}ed'.format(action),
    ]

    os.remove(pw_file)


@pytest.mark.parametrize('action', ['remove', 'delete'])
def test_remove(action, capsys):
    create_default()
    process('user {} Alice'.format(action))
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Alice has been {}d'.format(action)
    assert not err


@pytest.mark.parametrize('action', ['remove', 'delete'])
def test_remove_not_exist(action, capsys):
    create_default()
    process('user {} Dirac'.format(action))
    out, err = capsys.readouterr()
    assert not err
    assert out.rstrip() == "ValueError: Cannot {} 'Dirac'. This " \
                           "user is not in the table.".format(action)


def test_update(capsys):
    create_default()
    process('user update Alice')
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Updated Alice'
    assert not err


def test_update_password(capsys):
    create_default()
    process('user update Alice --password pw')
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Updated Alice'
    assert not err


def test_update_admin(capsys):
    create_default()
    process('user update Alice --admin')
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Updated Alice'
    assert not err


def test_update_password_file(capsys):
    create_default()
    pw_file = os.path.join(tempfile.gettempdir(), 'password.tmp')
    with open(pw_file, mode='wt') as fp:
        fp.write('a password in a file')

    process('user update Alice --password {}'.format(pw_file))
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        'Reading the password from the file',
        'Updated Alice',
    ]

    os.remove(pw_file)


def test_update_not_exist(capsys):
    create_default()
    process('user update Dirac')
    out, err = capsys.readouterr()
    assert not err
    assert out.rstrip() == "ValueError: Cannot update 'Dirac'. This " \
                           "user is not in the table."
