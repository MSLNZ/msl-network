"""
Example :class:`~msl.network.service.Service` for manipulating arrays.

Before running this module ensure that the Network :class:`~msl.network.manager.Manager`
is running on the same computer (i.e., run ``msl-network start`` in a terminal
to start the Network :class:`~msl.network.manager.Manager`).

After the ``Array`` :class:`~msl.network.service.Service` starts you can
:obj:`~msl.network.client.connect` a :class:`~msl.network.client.Client` to the
Network :class:`~msl.network.manager.Manager` to request the ``Array``
:class:`~msl.network.service.Service` to perform a task.
"""
from msl.network import Service


class Array(Service):

    def linspace(self, start, stop, n=100):
        """Return evenly spaced numbers over a specified interval."""
        log.info(f'Array.linspace({start}, {stop}, {n})')
        t0 = time.perf_counter()
        if n == 1:
            n = 2
            dx = stop - start
        else:
            dx = (stop-start)/(n-1.0)
        values = [start+i*dx for i in range(int(n))]
        log.info('linspace took {:.3g} seconds'.format(time.perf_counter() - t0))
        return values

    def scalar_multiply(self, scalar, array):
        """Multiply every element in the array by a scalar value."""
        log.info(f'Array.scalar_multiply({scalar}, array_len={len(array)})')
        t0 = time.perf_counter()
        values = [element*scalar for element in array]
        log.info('scalar_multiply took {:.3g} seconds'.format(time.perf_counter() - t0))
        return values


if __name__ == '__main__':
    import time
    import logging

    debug = True

    log = logging.getLogger('array')
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s [%(levelname)-5s] %(name)s - %(message)s',
    )

    service = Array()
    service.start(debug=debug)
