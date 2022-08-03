import re
import platform

import pytest

import conftest

from msl.network import connect
from msl.network.constants import HOSTNAME, LOCALHOST_ALIASES
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
    for alias in LOCALHOST_ALIASES:
        assert alias in hostnames

    with pytest.raises(ValueError, match=r'Cannot make asynchronous requests'):
        cxn.admin_request('users_table.usernames', asynchronous=True)

    manager.shutdown(connection=cxn)


def test_manager_identity():
    manager = conftest.Manager(BasicMath, MyArray, Echo)

    cxn = connect(name='A.B.C', **manager.kwargs)

    os = f'{platform.system()} {platform.release()} {platform.machine()}'
    language = 'Python ' + platform.python_version()

    identities = cxn.identities()
    assert identities['hostname'] == HOSTNAME
    assert identities['port'] == manager.port
    assert identities['attributes'] == {
        'identity': '() -> dict',
        'link': '(service: str) -> bool'
    }
    assert identities['language'] == language
    assert identities['os'] == os
    assert f'A.B.C[{HOSTNAME}:{cxn.port}]' in identities['clients']
    assert 'BasicMath' in identities['services']
    assert 'Echo' in identities['services']
    assert 'MyArray' in identities['services']

    identities = cxn.identities(as_string=True)
    expected = fr'''Manager\[{HOSTNAME}:\d+]
  attributes:
    identity\(\) -> dict
    link\(service: str\) -> bool
  language: {language}
  os: {os}
Clients \[1]:
  A.B.C\[{HOSTNAME}:\d+]
    language: {language}
    os: {os}
Services \[3]:
  BasicMath\[{HOSTNAME}:\d+]
    attributes:
      add\(x:\s?Union\[int, float], y:\s?Union\[int, float]\) -> Union\[int, float]
      divide\(x:\s?Union\[int, float], y:\s?Union\[int, float]\) -> Union\[int, float]
      ensure_positive\(x:\s?Union\[int, float]\) -> bool
      euler\(\) -> 2.718281828459045
      multiply\(x:\s?Union\[int, float], y:\s?Union\[int, float]\) -> Union\[int, float]
      pi\(\) -> 3.141592653589793
      power\(x:\s?Union\[int, float], n=2\) -> Union\[int, float]
      set_logging_level\(level:\s?Union\[str, int]\) -> bool
      subtract\(x:\s?Union\[int, float], y:\s?Union\[int, float]\) -> Union\[int, float]
    language: {language}
    max_clients: -1
    os: {os}
  Echo\[{HOSTNAME}:\d+]
    attributes:
      echo\(\*args, \*\*kwargs\)
      set_logging_level\(level:\s?Union\[str, int]\) -> bool
    language: {language}
    max_clients: -1
    os: {os}
  MyArray\[{HOSTNAME}:\d+]
    attributes:
      linspace\(start:\s?Union\[int, float], stop:\s?Union\[int, float], n=100\) -> List\[float]
      scalar_multiply\(scalar:\s?Union\[int, float], data:\s?List\[float]\) -> List\[float]
      set_logging_level\(level:\s?Union\[str, int]\) -> bool
    language: {language}
    max_clients: -1
    os: {os}
'''.splitlines()

    id_lines = identities.splitlines()
    assert len(id_lines) == len(expected)

    for pattern, string in zip(expected, id_lines):
        assert re.match(pattern, string)

    manager.shutdown(connection=cxn)


def test_not_json_serializable():
    manager = conftest.Manager(Echo)
    cxn = connect(**manager.kwargs)
    e = cxn.link('Echo')
    with pytest.raises(TypeError, match=r'not JSON serializable'):
        e.echo(1 + 4j)
    manager.shutdown(connection=cxn)
