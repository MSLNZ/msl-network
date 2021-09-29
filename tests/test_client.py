import re
import platform

import conftest

from msl.network import connect
from msl.network.utils import localhost_aliases, HOSTNAME
from msl.examples.network import BasicMath, MyArray, Echo


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


def test_manager_identity():
    manager = conftest.Manager(BasicMath, MyArray, Echo)

    cxn = connect(name='A.B.C', **manager.kwargs)

    os = '{} {} {}'.format(platform.system(), platform.release(), platform.machine())
    language = 'Python ' + platform.python_version()

    identity = cxn.manager()
    assert identity['hostname'] == HOSTNAME
    assert identity['port'] == manager.port
    assert identity['attributes'] == {
        'identity': '() -> dict',
        'link': '(service: str) -> bool'
    }
    assert identity['language'] == language
    assert identity['os'] == os
    assert 'A.B.C[{}:{}]'.format(HOSTNAME, cxn.port) in identity['clients']
    assert 'BasicMath' in identity['services']
    assert 'Echo' in identity['services']
    assert 'MyArray' in identity['services']

    identity = cxn.manager(as_string=True)
    expected = r'''Manager\[{hostname}:\d+]
  attributes:
    identity\(\) -> dict
    link\(service: str\) -> bool
  language: {language}
  os: {os}
Clients \[1]:
  A.B.C\[{hostname}:\d+]
    language: {language}
    os: {os}
Services \[3]:
  BasicMath\[{hostname}:\d+]
    attributes:
      add\(x:\s?Union\[int, float], y:\s?Union\[int, float]\) -> Union\[int, float]
      divide\(x:\s?Union\[int, float], y:\s?Union\[int, float]\) -> Union\[int, float]
      ensure_positive\(x:\s?Union\[int, float]\) -> bool
      euler\(\) -> 2.718281828459045
      multiply\(x:\s?Union\[int, float], y:\s?Union\[int, float]\) -> Union\[int, float]
      pi\(\) -> 3.141592653589793
      power\(x:\s?Union\[int, float], n=2\) -> Union\[int, float]
      subtract\(x:\s?Union\[int, float], y:\s?Union\[int, float]\) -> Union\[int, float]
    language: {language}
    max_clients: -1
    os: {os}
  Echo\[{hostname}:\d+]
    attributes:
      echo\(\*args, \*\*kwargs\)
    language: {language}
    max_clients: -1
    os: {os}
  MyArray\[{hostname}:\d+]
    attributes:
      linspace\(start:\s?Union\[int, float], stop:\s?Union\[int, float], n=100\) -> List\[float]
      scalar_multiply\(scalar:\s?Union\[int, float], data:\s?List\[float]\) -> List\[float]
    language: {language}
    max_clients: -1
    os: {os}
'''.format(hostname=HOSTNAME, language=language, os=os).splitlines()

    id_lines = identity.splitlines()
    assert len(id_lines) == len(expected)

    for pattern, string in zip(expected, id_lines):
        assert re.match(pattern, string)

    manager.shutdown(connection=cxn)
