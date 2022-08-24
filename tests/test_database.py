import datetime
import socket

import pytest

from msl.network import database


def test_users_table():

    table = database.UsersTable(database=':memory:')

    users = [
        ('admin', 'the administrator', True),
        ('enforcer', 'the second in command', 1),
        ('Alice', 'alice123', False),
        ('Bob', 'bob likes cheese', []),
        ('charlie', 'CharliesAngels', 0),
        ('jdoe2', 'anonymous & unknown', None),  # username can end with an integer
    ]

    for user in users:
        table.insert(*user)

    with pytest.raises(ValueError):
        table.insert('myname:1234', 'whatever', False)  # username cannot end with ":integer"

    user = table.get_user('admin')
    assert user[1] == 'admin'
    assert isinstance(user[2], bytes)
    assert isinstance(user[3], bytes)
    assert user[4]

    assert not table.get_user('does not exist')

    with pytest.raises(ValueError):
        table.insert('Alice', 'whatever', 0)  # an Alice already exists in the table

    assert len(table.usernames()) == 6
    assert 'admin' in table.usernames()
    assert 'enforcer' in table.usernames()
    assert 'Alice' in table.usernames()
    assert 'Bob' in table.usernames()
    assert 'charlie' in table.usernames()
    assert 'jdoe2' in table.usernames()

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

    assert not table.is_admin('jdoe2')
    assert not table.is_password_valid('jdoe2', 'wrong password')
    assert table.is_password_valid('jdoe2', 'anonymous & unknown')
    table.update('jdoe2', password='password123ABC')
    assert not table.is_admin('jdoe2')
    assert table.is_password_valid('jdoe2', 'password123ABC')

    assert table.is_admin('enforcer')
    assert table.is_password_valid('enforcer', 'the second in command')
    assert not table.is_admin('charlie')
    table.update('enforcer', is_admin=False)
    assert not table.is_admin('charlie')
    assert table.is_password_valid('enforcer', 'the second in command')
    assert not table.is_admin('enforcer')

    with pytest.raises(ValueError):
        table.delete('does not exist')

    table.delete('jdoe2')
    assert 'jdoe2' not in table.usernames()

    for name, is_admin in table.users():
        assert isinstance(name, str)
        assert isinstance(is_admin, bool)
        if name in ('admin', 'Bob'):
            assert is_admin
        else:
            assert not is_admin

    for record in table.records():
        table.delete(record[1])
    assert not table.usernames()


def test_hostnames_table():

    table = database.HostnamesTable(database=':memory:')

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

    connections = [
        (Peer('192.168.1.100', 'MSL.domain.nz', 7614), 'message 1'),
        (Peer('192.168.1.100', 'MSL.domain.nz', 21742), 'message 2'),
        (Peer('192.168.1.200', 'MSL.domain.nz', 51942), 'message 3'),
    ]

    table = database.ConnectionsTable(database=':memory:', as_datetime=False)
    for peer, message in connections:
        table.insert(peer, message)

    for connection in table.connections():
        assert len(connection) == 6
        for i in range(6):
            if i == 0 or i == 4:
                assert isinstance(connection[i], int)
            else:
                assert isinstance(connection[i], str)

    table = database.ConnectionsTable(database=':memory:', as_datetime=True)
    for peer, message in connections:
        table.insert(peer, message)

    for connection in table.connections():
        assert len(connection) == 6
        for i in range(6):
            if i == 0 or i == 4:
                assert isinstance(connection[i], int)
            elif i == 1:
                assert isinstance(connection[i], datetime.datetime)
            else:
                assert isinstance(connection[i], str)
