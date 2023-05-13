import platform

import pytest

import conftest
from msl.examples.network import Echo
from msl.network import LinkedClient
from msl.network.constants import HOSTNAME


def test_linked_echo():

    manager = conftest.Manager(Echo)

    manager.kwargs['name'] = 'foobar'
    link = LinkedClient('Echo', **manager.kwargs)

    args, kwargs = link.echo(1, 2, 3)
    assert len(args) == 3
    assert args[0] == 1
    assert args[1] == 2
    assert args[2] == 3
    assert len(kwargs) == 0

    args, kwargs = link.echo(x=4, y=5, z=6)
    assert len(args) == 0
    assert kwargs['x'] == 4
    assert kwargs['y'] == 5
    assert kwargs['z'] == 6

    args, kwargs = link.echo(1, 2, 3, x=4, y=5, z=6)
    assert len(args) == 3
    assert args[0] == 1
    assert args[1] == 2
    assert args[2] == 3
    assert kwargs['x'] == 4
    assert kwargs['y'] == 5
    assert kwargs['z'] == 6

    assert len(link.service_attributes) == 2
    assert 'echo' in link.service_attributes
    assert 'set_logging_level' in link.service_attributes
    assert link.name == 'foobar'
    assert link.address_manager.startswith('localhost:')
    assert isinstance(link.port, int)
    assert link.service_address.startswith(f'{HOSTNAME}:')
    assert link.is_connected() is True
    assert link.service_name == 'Echo'
    assert link.service_language == f'Python {platform.python_version()}'
    assert link.service_os == f'{platform.system()} {platform.release()} {platform.machine()}'
    assert link.service_max_clients == -1

    ids = link.identities()
    assert 'Echo' in ids['services']
    assert str(link.client) in ids['clients']
    assert str(link.client).startswith('foobar')

    with pytest.raises(RuntimeError, match=r"'Echo' object has no attribute"):
        link.does_not_exist()

    assert str(link).startswith('<Link[name=foobar] with Echo[')
    link.unlink()
    assert str(link).startswith('<Un-Linked[name=foobar] from Echo[')

    with pytest.raises(AttributeError, match=r"Cannot access 'echo'"):
        link.echo(0)

    link2 = link.spawn()
    assert str(link2).startswith('<Link[name=LinkedClient] with Echo[')
    assert str(link2.client) == f'LinkedClient[{HOSTNAME}:{link2.port}]'
    assert link2.echo('echo', cold='fusion') == [['echo'], {'cold': 'fusion'}]
    link2.disconnect()
    assert str(link2).startswith('<Un-Linked[name=LinkedClient] from Echo[')
    assert link2.client is None
    assert link2.is_connected() is False

    manager.shutdown(connection=link.client)
