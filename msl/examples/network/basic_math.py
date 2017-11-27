"""
Example :class:`~msl.network.service.Service` for performing basic math operations.

Before running this module ensure that the Network :class:`~msl.network.manager.Manager`
is running on the same computer (i.e., run ``msl-network start`` in a terminal
to start the Network :class:`~msl.network.manager.Manager`).

After the ``BasicMath`` :class:`~msl.network.service.Service` starts you can
:obj:`~msl.network.client.connect` a :class:`~msl.network.client.Client` to the
Network :class:`~msl.network.manager.Manager` to request the ``BasicMath``
:class:`~msl.network.service.Service` to perform a task.
"""
from msl.network import Service


class BasicMath(Service):

    euler = 2.7182818

    @property
    def pi(self):
        return 3.1415926

    def add(self, x: int, y: int) -> int:
        log.info('add -- sleeping for 1 second')
        time.sleep(1)
        return x + y

    def subtract(self, x: int, y: int) -> int:
        log.info('subtract -- sleeping for 2 seconds')
        time.sleep(2)
        return x - y

    def multiply(self, x: float, y: float) -> float:
        log.info('multiply -- sleeping for 3 seconds')
        time.sleep(3)
        return x * y

    def divide(self, x: float, y: float) -> float:
        log.info('divide -- sleeping for 4 seconds')
        time.sleep(4)
        return x / float(y)

    def error_if_negative(self, x: float) -> bool:
        log.info('error_if_negative -- sleeping for 5 seconds')
        time.sleep(5)
        if x < 0:
            raise ValueError('The value is < 0')
        return True

    def power(self, x: float, n: int =2) -> float:
        log.info('power -- sleeping for 6 seconds')
        time.sleep(6)
        return x ** n


if __name__ == '__main__':
    import time
    import logging

    debug = True

    log = logging.getLogger('basic_math')
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s [%(levelname)-5s] %(name)s - %(message)s',
    )

    service = BasicMath()
    service.start(debug=debug)
