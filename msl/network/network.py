"""
Base class for all Managers, Services and Clients.
"""
import json
import asyncio
import traceback


class Network(object):
    """Base class for all Managers, Services and Clients."""

    encoding = 'utf-8'
    """:obj:`str`: The encoding to use to convert a :obj:`str` to :obj:`bytes`."""

    def identity(self):
        """Identify oneself on the network.

        All network objects must be able to identify themselves to any
        device that is connected to the network. There are 3 possible types
        of network objects -- Manager, Service, Client. The member names and
        JSON_ datatype for each network object is described below.

        * Manager
          - hostname : string
              The name of the device that the Manager is running on.
          - port : integer
              The port number that the Manager is running on.
          - language : string
              The programming language that the Manager is running on.
          - os : string
              The operating system that the Manager is running on.
          - clients : array
              An array (a Python list) of clients that are currently
              connected to the Manager.
          - services : object
              An object (a Python dictionary) of services that are currently
              connected to the Manager.
          - manager : object
              An object (a Python dictionary) of attributes that the
              Manager provides.

        * Service
          - type : string
              This must be equal to "service" (case-insensitive).
          - name : string
              The name of the service (can contain spaces).
          - attributes : object
              An object (a Python dictionary) of attributes that the
              Service provides.
          - address : string, optional
              The hostname and port number (separated by a colon) that
              the Service is running on.
          - language : string, optional
              The programming language that the Service is running on.
              Default is null.
          - os : string, optional
              The operating system that the Service is running on.
              Default is null.

        * Client
          - type : string
              This must be equal to "client" (case-insensitive).

        Returns
        -------
        The identity of the network object in JSON_ format.

        .. _JSON: http://www.json.org/
        """
        raise NotImplementedError

    def send_data(self, writer, data):
        """Send `data` as a JSON_ string.

        Converts `data` to a JSON_ string, appends the line-feed character
        (``0x0A``, ``\n``), encodes the resultant string to bytes and then
        sends the bytes through the network.

        Parameters
        ----------
        writer : :class:`asyncio.Transport` or :class:`asyncio.StreamWriter`
            The writer.
        data : :obj:`object`
            Any object that can be serialized into a JSON_ string.

        .. _JSON: http://www.json.org/
        """
        try:
            writer.write((json.dumps(data) + '\n').encode(self.encoding))
        except (json.JSONDecodeError, TypeError) as e:
            # get TypeError if an object is not JSON serializable
            self.send_error(writer, e)

    def send_error(self, writer, error):
        """Send an error through the network.

        Parameters
        ----------
        writer : :class:`asyncio.Transport` or :class:`asyncio.StreamWriter`
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

        Parameters
        ----------
        writer : :class:`asyncio.Transport` or :class:`asyncio.StreamWriter`
            The writer.
        reply : :obj:`object`
            Any object that can be serialized into a JSON_ string.

        .. _JSON: http://www.json.org/
        """
        self.send_data(writer, {'error': False, 'return': reply})

    def send_request(self, writer, attribute, parameters=None, service=''):
        """Send a request through the network.

        Parameters
        ----------
        writer : :class:`asyncio.Transport` or :class:`asyncio.StreamWriter`
            The writer.
        attribute : :obj:`str`
            The name of an attribute that the request . For example, the name
            of a method or variable.
        parameters : :obj:`dict`, optional
            The key-value pairs that the `attribute` requires.
        service : :obj:`str`, optional
            The name of an service to handle the request. Only a client that is
            sending the request must specify the service it wants to connect to.
            Set `service` to :obj:`None` to request something from the Manager.

        .. _JSON: http://www.json.org/
        """
        if parameters is None:
            parameters = {}
        if service is None or service:  # then the request comes from a client
            self.send_data(writer, {'service': service, 'attribute': attribute, 'parameters': parameters})
        else:  # the request comes from the manager
            self.send_data(writer, {'error': False, 'attribute': attribute, 'parameters': parameters})
