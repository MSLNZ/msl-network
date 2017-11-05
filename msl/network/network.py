"""
Base class for all :class:`~msl.network.manager.Manager`'\s,
:class:`~msl.network.service.Service`'\s and :class:`~msl.network.client.Client`'\s.
"""
import json
import asyncio
import logging
import traceback

log = logging.getLogger(__name__)


class Network(object):
    """
    Base class for all :class:`~msl.network.manager.Manager`'\s,
    :class:`~msl.network.service.Service`'\s and :class:`~msl.network.client.Client`'\s.
    """

    encoding = 'utf-8'
    """:obj:`str`: The encoding to use to convert a :obj:`str` to :obj:`bytes`."""

    _debug = False
    _network_id = None

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

            - language : string
                The programming language that the Network :class:`~msl.network.manager.Manager` is running on.

            - os : string
                The operating system that the :class:`~msl.network.manager.Manager` is running on.

            - attributes : object
                An object (a Python dictionary) of attributes that the Network
                :class:`~msl.network.manager.Manager` provides.

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

            - address : string, optional
                The hostname and port number (separated by a colon) that
                the :class:`~msl.network.service.Service` is running on.

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
            The bytes to send, terminated with the line-feed character.
        """
        if self._debug:
            log.debug(f'{self._network_id} sent {line}')
        writer.write(line)

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
            self.send_line(writer, (json.dumps(data) + '\n').encode(self.encoding))
        except (json.JSONDecodeError, TypeError) as e:
            # get TypeError if an object is not JSON serializable
            self.send_error(writer, e)

    def send_error(self, writer, error):
        """Send an error through the network.

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer.
        error : :class:`Exception`
            An exception object.
        """
        tb = traceback.format_exc()
        message = error.__class__.__name__ + ': ' + str(error)
        self.send_data(writer, {
            'error': True,
            'return': None,
            'message': message,
            'traceback': [message] if tb.startswith('NoneType:') else tb.splitlines(),
        })

    def send_reply(self, writer, reply):
        """Send a reply through the network.

        .. _JSON: http://www.json.org/

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer.
        reply : :obj:`object`
            Any object that can be serialized into a JSON_ string.
        """
        self.send_data(writer, {'return': reply, 'error': False})

    def send_request(self, writer, attribute, parameters=None, service=''):
        """Send a request through the network.

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer.
        attribute : :obj:`str`
            The name of an attribute that the request . For example, the name
            of a method or variable.
        parameters : :obj:`dict`, optional
            The key-value pairs that the `attribute` requires.
        service : :obj:`str`, optional
            The name of a :class:`~msl.network.service.Service` to handle the request.
            Only a :class:`~msl.network.client.Client` that is sending the request must
            specify the service it wants to connect to. Set `service` to :obj:`None`
            to send a request from the Network :class:`~msl.network.manager.Manager`.
        """
        if parameters is None:
            parameters = {}
        if service is None or service:  # then the request comes from a Client
            self.send_data(writer, {'service': service, 'attribute': attribute, 'parameters': parameters})
        else:  # the request comes from the Manager
            self.send_data(writer, {'attribute': attribute, 'parameters': parameters, 'error': False})
