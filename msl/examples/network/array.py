"""
Example :class:`~msl.network.service.Service` for generating and manipulating arrays.

Before running this module ensure that the Network :class:`~msl.network.manager.Manager`
is running on the same computer (i.e., run ``msl-network start`` in a terminal
to start the Network :class:`~msl.network.manager.Manager`).

After the ``Array`` :class:`~msl.network.service.Service` starts you can
:obj:`~msl.network.client.connect` to the Network :class:`~msl.network.manager.Manager`,
:meth:`~msl.network.client.Client.link` with the ``Array`` :class:`~msl.network.service.Service`
and then have the ``Array`` :class:`~msl.network.service.Service` execute tasks.
"""
from msl.network import Service


class Array(Service):

    def linspace(self, start, stop, n=100):
        """Return evenly spaced numbers over a specified interval."""
        dx = (stop-start)/float(n-1)
        return [start+i*dx for i in range(int(n))]

    def scalar_multiply(self, scalar, array):
        """Multiply every element in the array by a scalar value."""
        return [element*scalar for element in array]


if __name__ == '__main__':
    import logging

    # allows for "info" log messages to be visible from the Service
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-5s] %(name)s - %(message)s', )

    service = Array()
    service.start()
