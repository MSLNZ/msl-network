"""
Example Service for generating and manipulating arrays. This example
illustrates how to interface a LabVIEW program with MSL-Network.

Before running this module ensure that the Network Manager is running on the
same computer, i.e., run the following command in a terminal

msl-network start

then run this module to connect to the Manager as a Service.

After the MyArray Service starts you can connect to the Manager as a Client,
link with the MyArray Service and then send requests, e.g.,

from msl.network import connect
cxn = connect()
my_array = cxn.link('MyArray')
linspace = my_array.linspace(0, 1)
"""
from typing import List, Union

from msl.network import Service

number = Union[int, float]
Vector = List[float]


class MyArray(Service):

    @staticmethod
    def linspace(start: number, stop: number, n=100) -> List[float]:
        """Return evenly-spaced numbers over a specified interval."""
        dx = (stop-start)/float(n-1)
        return [start+i*dx for i in range(int(n))]

    @staticmethod
    def scalar_multiply(scalar: number, data: Vector) -> Vector:
        """Multiply every element in `data` by a number."""
        return [element*scalar for element in data]


if __name__ == '__main__':
    service = MyArray()
    service.start()
