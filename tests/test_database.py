import socket
import datetime

import pytest

from msl.network import database


def test_users_table():

    table = database.UsersTable(':memory:')

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

    user = table.get_user('admin')
    assert user['username'] == 'admin'
    assert isinstance(user['key'], bytes)
    assert isinstance(user['salt'], bytes)
    assert user['is_admin']

    assert not table.get_user('does not exist')

    with pytest.raises(ValueError):
        table.insert('Alice', 'whatever', 0)

    assert len(table.usernames()) == 6
    assert 'admin' in table.usernames()
    assert 'enforcer' in table.usernames()
    assert 'Alice' in table.usernames()
    assert 'Bob' in table.usernames()
    assert 'charlie' in table.usernames()
    assert 'jdoe' in table.usernames()

    with pytest.raises(ValueError):
        table.update('does not exist')

    with pytest.raises(ValueError):
        table.update('Alice')  # must specify password, is_admin or both

    assert table.is_password_valid('Bob', 'bob likes cheese')
    assert not table.is_password_valid('Bob', 'kjharg84h')
    assert not table.is_admin('Bob')
    table.update('Bob', password='my new password', is_admin=True)
    assert table.is_admin('Bob')
    assert not table.is_password_valid('Bob', 'bob likes cheese')
    assert table.is_password_valid('Bob', 'my new password')

    assert not table.is_admin('jdoe')
    assert not table.is_password_valid('jdoe', 'wrong password')
    assert table.is_password_valid('jdoe', 'anonymous & unknown')
    table.update('jdoe', password='password123ABC')
    assert not table.is_admin('jdoe')
    assert table.is_password_valid('jdoe', 'password123ABC')

    assert table.is_admin('enforcer')
    assert table.is_password_valid('enforcer', 'the second in command')
    assert not table.is_admin('charlie')
    table.update('enforcer', is_admin=False)
    assert not table.is_admin('charlie')
    assert table.is_password_valid('enforcer', 'the second in command')
    assert not table.is_admin('enforcer')

    with pytest.raises(ValueError):
        table.delete('does not exist')

    table.delete('jdoe')
    assert 'jdoe' not in table.usernames()

    for name, is_admin in table.users():
        assert isinstance(name, str)
        assert isinstance(is_admin, bool)
        if name in ('admin', 'Bob'):
            assert is_admin
        else:
            assert not is_admin

    for record in table.records():
        table.delete(record['username'])
    assert not table.usernames()


def test_hostnames_table():

    table = database.HostnamesTable(':memory:')

    # all localhost aliases are added if the table is empty
    assert 'localhost' in table.hostnames()
    assert '127.0.0.1' in table.hostnames()
    assert '::1' in table.hostnames()
    assert socket.gethostname() in table.hostnames()

    with pytest.raises(ValueError):
        table.delete('unknown hostname')

    table.insert('HOSTNAME')

    assert 'HOSTNAME' in table.hostnames()
    table.delete('HOSTNAME')
    assert 'HOSTNAME' not in table.hostnames()


def test_connections_table():

    class Peer(object):
        def __init__(self, ip_address, domain, port):
            self.ip_address = ip_address
            self.domain = domain
            self.port = port

    table = database.ConnectionsTable(':memory:')

    connections = [
        (Peer('192.168.1.100', 'MSL.domain.nz', 7614), 'message 1'),
        (Peer('192.168.1.100', 'MSL.domain.nz', 21742), 'message 2'),
        (Peer('192.168.1.200', 'MSL.domain.nz', 51942), 'message 3'),
    ]

    for peer, message in connections:
        table.insert(peer, message)

    for connection in table.connections():
        assert len(connection) == 6
        for i in range(6):
            if i == 0 or i == 4:
                assert isinstance(connection[i], int)
            else:
                assert isinstance(connection[i], str)

    for connection in table.connections(False):
        assert len(connection) == 6
        for i in range(6):
            if i == 0 or i == 4:
                assert isinstance(connection[i], int)
            elif i == 1:
                assert isinstance(connection[i], datetime.datetime)
            else:
                assert isinstance(connection[i], str)
