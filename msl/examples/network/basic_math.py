"""
Example :class:`~msl.network.service.Service` for performing basic math operations.

Before running this module ensure that the Network :class:`~msl.network.manager.Manager`
is running on the same computer (i.e., run ``msl-network start`` in a terminal
to start the Network :class:`~msl.network.manager.Manager`).

After the ``BasicMath`` :class:`~msl.network.service.Service` starts you can
:meth:`~msl.network.client.connect` to the Network :class:`~msl.network.manager.Manager`,
:meth:`~msl.network.client.Client.link` with the ``BasicMath`` :class:`~msl.network.service.Service`
and then have the ``BasicMath`` :class:`~msl.network.service.Service` execute tasks.
"""
import time
from typing import Union

from msl.network import Service

number = Union[int, float]


class BasicMath(Service):

    euler = 2.718281828459045

    @property
    def pi(self) -> float:
        return 3.141592653589793

    def add(self, x:number, y:number) -> number:
        time.sleep(1)
        return x + y

    def subtract(self, x:number, y:number) -> number:
        time.sleep(2)
        return x - y

    def multiply(self, x:number, y:number) -> number:
        time.sleep(3)
        return x * y

    def divide(self, x:number, y:number) -> number:
        time.sleep(4)
        return x / float(y)

    def ensure_positive(self, x:number) -> bool:
        time.sleep(5)
        if x < 0:
            raise ValueError('The value is < 0')
        return True

    def power(self, x:number, n=2) -> number:
        time.sleep(6)
        return x ** n


if __name__ == '__main__':
    import logging

    # allows for "info" log messages to be visible from the Service
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)-5s] %(name)s - %(message)s',
    )

    service = BasicMath()
    service.start()
