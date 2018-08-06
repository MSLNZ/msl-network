"""
Example echo :class:`~msl.network.service.Service`.

Before running this module ensure that the Network :class:`~msl.network.manager.Manager`
is running on the same computer (i.e., run ``msl-network start`` in a terminal
to start the Network :class:`~msl.network.manager.Manager`).

After the ``Echo`` :class:`~msl.network.service.Service` starts you can
:meth:`~msl.network.client.connect` to the Network :class:`~msl.network.manager.Manager`,
and :meth:`~msl.network.client.Client.link` with the ``Echo`` :class:`~msl.network.service.Service`.
"""
from msl.network import Service


class Echo(Service):

    def echo(self, *args, **kwargs):
        return args, kwargs


if __name__ == '__main__':
    service = Echo()
    service.start()
