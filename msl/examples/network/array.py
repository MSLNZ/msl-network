"""
Example :class:`~msl.network.service.Service` for generating and manipulating arrays.

Before running this module ensure that the Network :class:`~msl.network.manager.Manager`
is running on the same computer (i.e., run ``msl-network start`` in a terminal
to start the Network :class:`~msl.network.manager.Manager`).

After the ``MyArray`` :class:`~msl.network.service.Service` starts you can
:meth:`~msl.network.client.connect` to the Network :class:`~msl.network.manager.Manager`,
:meth:`~msl.network.client.Client.link` with the ``MyArray`` :class:`~msl.network.service.Service`
and then have the ``MyArray`` :class:`~msl.network.service.Service` execute tasks.
"""
from typing import List, Union

from msl.network import Service

number = Union[int, float]
Vector = List[float]


class MyArray(Service):

    def linspace(self, start:number, stop:number, n=100) -> List[float]:
        """Return evenly spaced numbers over a specified interval."""
        dx = (stop-start)/float(n-1)
        return [start+i*dx for i in range(int(n))]

    def scalar_multiply(self, scalar:number, data:Vector) -> Vector:
        """Multiply every element in `data` by a number."""
        return [element*scalar for element in data]


if __name__ == '__main__':
    import logging

    # allows for "info" log messages to be visible from the Service
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)-5s] %(name)s - %(message)s',
    )

    service = MyArray()
    service.start()
