import conftest

from msl.network import connect
from msl.network.utils import localhost_aliases


def test_admin_requests():
    manager = conftest.Manager()

    cxn = connect(**manager.kwargs)

    assert cxn.admin_request('port') == manager.port
    assert cxn.admin_request('password') is None
    assert cxn.admin_request('login')
    assert cxn.admin_request('hostnames') is None

    assert cxn.admin_request('users_table.is_user_registered', manager.admin_username) is True
    assert cxn.admin_request('users_table.is_password_valid', manager.admin_username, manager.admin_password) is True
    assert cxn.admin_request('users_table.is_admin', manager.admin_username) is True
    assert cxn.admin_request('users_table.is_user_registered', 'no one special') is False

    conns = cxn.admin_request('connections_table.connections')
    assert len(conns) == 2
    assert conns[0][4] == cxn.port
    assert conns[0][5] == 'new connection request'
    assert conns[1][4] == cxn.port
    assert conns[1][5] == 'connected as a client'

    hostnames = cxn.admin_request('hostnames_table.hostnames')
    for alias in localhost_aliases():
        assert alias in hostnames

    manager.shutdown(connection=cxn)
