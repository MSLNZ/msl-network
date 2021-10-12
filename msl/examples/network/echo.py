"""
Example echo Service.

Before running this module ensure that the Network Manager is running on the
same computer, i.e., run the following command in a terminal

msl-network start

then run this module to connect to the Manager as a Service.

After the Echo Service starts you can connect to the Manager as a Client,
link with the Echo Service and then send requests, e.g.,

from msl.network import connect
cxn = connect()
e = cxn.link('Echo')
args, kwargs = e.echo(1, 2, x='hello', y='world')
"""
from msl.network import Service


class Echo(Service):

    @staticmethod
    def echo(*args, **kwargs):
        return args, kwargs


if __name__ == '__main__':
    service = Echo()
    service.start()
