import helper  # located in the tests folder

from msl.network import connect
from msl.network.utils import localhost_aliases


def test_admin_requests():
    services = helper.ServiceStarter()

    cxn = connect(**services.kwargs)

    assert cxn.admin_request('port') == services.port
    assert cxn.admin_request('password') is None
    assert cxn.admin_request('login')
    assert cxn.admin_request('hostnames') is None

    assert cxn.admin_request('users_table.is_user_registered', services.admin_username)
    assert cxn.admin_request('users_table.is_password_valid', services.admin_username, services.admin_password)
    assert cxn.admin_request('users_table.is_admin', services.admin_username)
    assert not cxn.admin_request('users_table.is_user_registered', 'no one special')

    assert len(cxn.admin_request('connections_table.connections')) > 0
    conns = cxn.admin_request('connections_table.connections')
    # conns[0] and conns[1] are from the Client that is created in ServiceStarter
    assert conns[0][5] == 'new connection request'
    assert conns[1][4] == conns[0][4]
    assert conns[1][5] == 'connected as a client'
    assert conns[2][4] == conns[0][4]
    assert conns[2][5] == 'disconnected'
    assert conns[3][4] == cxn.port
    assert conns[3][5] == 'new connection request'
    assert conns[4][4] == cxn.port
    assert conns[4][5] == 'connected as a client'

    hostnames = cxn.admin_request('hostnames_table.hostnames')
    for alias in localhost_aliases():
        assert alias in hostnames

    services.shutdown(cxn)
