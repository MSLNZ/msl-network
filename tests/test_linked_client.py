import conftest

import pytest

from msl.network import LinkedClient, MSLNetworkError
from msl.examples.network import Echo


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

    assert len(link.service_attributes) == 1
    assert 'echo' in link.service_attributes
    assert link.name == 'foobar'

    with pytest.raises(MSLNetworkError):
        link.does_not_exist()

    manager.shutdown(connection=link.client)
