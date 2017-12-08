import helper  # located in the tests folder

from msl.network import connect
from msl.network.utils import localhost_aliases


def test_admin_requests():
    services = helper.ServiceStarter([])

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
    assert cxn.admin_request('connections_table.connections')[0][4] == cxn.port

    hostnames = cxn.admin_request('hostnames_table.hostnames')
    for alias in localhost_aliases():
        assert alias in hostnames

    services.shutdown(cxn)
