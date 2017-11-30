"""
Base class for all :class:`~msl.network.manager.Manager`'\s,
:class:`~msl.network.service.Service`'\s and :class:`~msl.network.client.Client`'\s.
"""
import time
import asyncio
import logging
import traceback

from .json import serialize

log = logging.getLogger(__name__)


class Network(object):
    """
    Base class for all Network :class:`~msl.network.manager.Manager`'\s,
    :class:`~msl.network.service.Service`'\s and :class:`~msl.network.client.Client`'\s.
    """

    encoding = 'utf-8'
    """:obj:`str`: The encoding to use to convert a :obj:`str` to :obj:`bytes`."""

    _network_name = None  # helpful for debugging who is sending what to where
    _max_print_size = 256  # the maximum number of characters to display when debugging

    def identity(self):
        """Identify oneself on the network.

        All devices on the network must be able to identify themselves to any
        other device that is connected to the network. There are 3 possible types
        of network devices -- :class:`~msl.network.manager.Manager`\'s,
        :class:`~msl.network.service.Service`\'s, :class:`~msl.network.client.Client`\'s.
        The member names and JSON_ datatype for each network device is described below.

        .. _JSON: http://www.json.org/

        * :class:`~msl.network.manager.Manager`

            - hostname : string
                The name of the device that the Network :class:`~msl.network.manager.Manager` is running on.

            - port : integer
                The port number that the Network :class:`~msl.network.manager.Manager` is running on.

            - attributes : object
                An object (a Python dictionary) of public attributes that the Network
                :class:`~msl.network.manager.Manager` provides. Users who are an administrator of
                the Network :class:`~msl.network.manager.Manager` can access private attributes.

            - language : string
                The programming language that the Network :class:`~msl.network.manager.Manager` is running on.

            - os : string
                The operating system that the :class:`~msl.network.manager.Manager` is running on.

            - clients : array
                An array (a Python list) of :class:`~msl.network.client.Client`\'s that are currently
                connected to the Network :class:`~msl.network.manager.Manager`.

            - services : object
                An object (a Python dictionary) of :class:`~msl.network.service.Service`\'s
                that are currently connected to the Network :class:`~msl.network.manager.Manager`.

        * :class:`~msl.network.service.Service`

            - type : string
                This must be equal to ``'service'`` (case-insensitive).

            - name : string
                The name to associated with the :class:`~msl.network.service.Service` (can contain spaces).

            - attributes : object
                An object (a Python dictionary) of attributes that the
                :class:`~msl.network.service.Service` provides.

            - language : string, optional
                The programming language that the :class:`~msl.network.service.Service` is running on.
                Default is null.

            - os : string, optional
                The operating system that the :class:`~msl.network.service.Service` is running on.
                Default is null.

        * :class:`~msl.network.client.Client`

            - type : string
                This must be equal to ``'client'`` (case-insensitive).

            - name : string
                The name to associate with the :class:`~msl.network.client.Client` (can contain spaces).

        Returns
        -------
        :obj:`dict`
            The identity of the network device in JSON_ format.
        """
        raise NotImplementedError

    def send_line(self, writer, line):
        """Send bytes through the network.

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer to use to send the bytes.
        line : :obj:`bytes`
            The bytes to send (that are already terminated with the line-feed character).
        """
        n = len(line)

        if self._debug:
            log.debug(f'{self._network_name} is sending {n} bytes')
            if n > self._max_print_size:
                log.debug(line[:self._max_print_size//2] + b' ... ' + line[-self._max_print_size//2:])
            else:
                log.debug(line)

        t0 = time.perf_counter()
        writer.write(line)

        if self._debug:
            dt = time.perf_counter() - t0
            if dt > 0:
                log.debug('{} sent {} bytes in {:.3g} seconds [{:.3f} MB/s]'.format(
                    self._network_name, n, dt, n*1e-6/dt))
            else:
                log.debug('{} sent {} bytes in {:.3f} useconds'.format(self._network_name, n, dt*1e6))

    def send_data(self, writer, data):
        """Serialize `data` as JSON_ bytes and send.

        Converts `data` to a JSON_ string, appends the line-feed character,
        encodes the resultant string to bytes and then sends the bytes
        through the network.

        .. _JSON: http://www.json.org/

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer to use to send the data.
        data : :obj:`object`
            Any object that can be serialized into a JSON_ string.
        """
        try:
            self.send_line(writer, (serialize(data) + '\n').encode(self.encoding))
        except Exception as e:
            self.send_error(writer, e, data['requester'])

    def send_error(self, writer, error, requester):
        """Send an error through the network.

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer.
        error : :class:`Exception`
            An exception object.
        requester : :obj:`str`
            The address, ``host:port``, of the device that sent the request.
        """
        tb = traceback.format_exc()
        message = error.__class__.__name__ + ': ' + str(error)
        self.send_data(writer, {
            'error': True,
            'message': message,
            'traceback': [message] if tb.startswith('NoneType:') else tb.splitlines(),
            'return': None,
            'requester': requester,
        })

    def send_reply(self, writer, reply, *, requester=None):
        """Send a reply through the network.

        :class:`~msl.network.client.Client`\'s, :class:`~msl.network.service.Service`\'s
        and the Network :class:`~msl.network.manager.Manager` can send replies.

        .. _JSON: http://www.json.org/

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer.
        reply : :obj:`object`
            Any object that can be serialized into a JSON_ string.
        requester : :obj:`str`
            The address, ``host:port``, of the device that sent the request.
            It is only mandatory to specify the address of the `requester` if a
            :class:`~msl.network.service.Service` is sending the reply.
        """
        self.send_data(writer, {'return': reply, 'requester': requester, 'error': False})
