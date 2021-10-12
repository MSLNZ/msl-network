"""
Example Service for illustrating the difference between synchronous and
asynchronous requests.

Before running this module ensure that the Network Manager is running on the
same computer, i.e., run the following command in a terminal

msl-network start

then run this module to connect to the Manager as a Service.

After the BasicMath Service starts you can connect to the Manager as a Client,
link with the BasicMath Service and then send requests, e.g.,

from msl.network import connect
cxn = connect()
bm = cxn.link('BasicMath')
value = bm.add(1, 2)
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

    # Optional: allows for "info" log messages to be visible on the Service
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)-5s] %(message)s',
    )

    service = BasicMath()
    service.start()
