"""
Base class for all Services.
"""
import json
import asyncio
import inspect
import logging
import platform

from .constants import PORT
from .network import Network
from .utils import get_ssl_context

log = logging.getLogger(__name__)

IGNORE_ITEMS = ['name', 'start', 'password'] + dir(Network) + dir(asyncio.Protocol)


class Service(Network, asyncio.Protocol):

    name = None
    """:obj:`str`: The name of the Service as it will appear on the Network :class:`~msl.network.manager.Manager`."""

    def __init__(self):
        """Base class for all Services."""
        self._loop = None
        self._password = None
        self._transport = None
        self._identity = dict()
        self._debug = None
        self._address = None
        self._address_manager = None
        if self.name is None:
            self.name = self.__class__.__name__
        self._network_id = self.name

    @property
    def address(self):
        """:obj:`str`: The address of this connection to the Network :class:`~msl.network.manager.Manager`."""
        return self._address

    @property
    def address_manager(self):
        """:obj:`str`: The address of the Network :class:`~msl.network.manager.Manager`."""
        return self._address_manager

    def __repr__(self):
        return '<{} at {:#x} manager={} address={}>'.format(self.name, id(self), self._address_manager, self._address)

    def password(self, hostname):
        """:obj:`str`: The password required to connect to the Network
        :class:`~msl.network.manager.Manager` at `hostname`."""
        if self._password is None:
            return input(f'Enter the password for {hostname}: ')
        return self._password

    def identity(self):
        """:obj:`dict`: The :obj:`~msl.network.network.Network.identity` of the :class:`Service`."""
        if not self._identity:
            self._identity['type'] = 'service'
            self._identity['name'] = self.name
            self._identity['language'] = 'Python ' + platform.python_version()
            self._identity['os'] = '{} {} {}'.format(platform.system(), platform.release(), platform.machine())
            self._identity['attributes'] = dict()
            for item in dir(self):
                if item.startswith('_') or item in IGNORE_ITEMS:
                    continue
                attrib = getattr(self, item)
                try:
                    value = str(inspect.signature(attrib))
                except TypeError:  # the the attribute is not a callable object
                    value = attrib
                self._identity['attributes'][item] = value
        return self._identity

    def connection_made(self, transport):
        """Automatically called when the connection to the Network
        :class:`~msl.network.manager.Manager` has been established."""
        self._address = '{}:{}'.format(*transport.get_extra_info('sockname'))
        self._network_id = '{}[{}]'.format(self.name, self._address)
        self._transport = transport
        log.info(f'{self} connection made')

    def data_received(self, data):
        """New data is received for the :class:`Service`.

        .. _JSON: http://www.json.org/

        Parameters
        ----------
        data : :obj:`bytes`
            A :class:`Service` receives data that will be converted into a JSON_ object.
            The input data **MUST** have one of the following formats.

            If the input data represents an error then the JSON_ object must be::

                {
                    'error' : bool (True)
                    'message': string (a short description of the error message)
                    'traceback': list of strings (a detailed stack trace of the error)
                }

            If the input data DOES NOT represent an error then the JSON_ object must be::

                {
                    'error' : bool (False)
                    'attribute': string (the name of a method or variable of the Service)
                    'parameters': object (key-value pairs to be passed to the Service's method)
                }

        Returns
        -------
        :obj:`bytes`
            The response from the :class:`Service`.

            A :class:`Service` will reply with a JSON_ object in one of the following formats.

            If the output data represents an error then the JSON_ object will be::

                {
                    'error' : bool (True)
                    'return': null
                    'message': string (a short description of the error)
                    'traceback': list of strings (a detailed stack trace of the error)
                }

            If the output data DOES NOT represent an error then the JSON_ object will be::

                {
                    'error' : bool (False)
                    'return': object (whatever the response is from the Service)
                }

        """
        if self._debug:
            log.debug(f'{self._network_id} received {data}')

        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            log.error(f'{self._network_id} {e.__class__.__name__}: {e}')
            self.send_error(self._transport, e)
            return

        if data.get('error', False):
            # then log the error message and don't send a reply back to the Manager
            try:
                msg = '\n'.join(data['traceback'])  # traceback should be a list of strings
            except:
                msg = data.get('message', 'Error: Unknown error')
            log.error(f'{self._network_id} {msg}')
            return

        try:
            attrib = getattr(self, data['attribute'])
        except Exception as e:
            log.error(f'{self._network_id} {e.__class__.__name__}: {e}')
            self.send_error(self._transport, e)
            return

        if callable(attrib):
            try:
                reply = attrib(**data['parameters'])
            except Exception as e:
                log.error(f'{self._network_id} {e.__class__.__name__}: {e}')
                self.send_error(self._transport, e)
                return
        else:
            reply = attrib

        self.send_reply(self._transport, reply)

    def connection_lost(self, exc):
        """Automatically called when the connection to the
        Network :class:`~msl.network.manager.Manager` has been closed."""
        log.info(f'{self} connection lost')
        self._transport = None
        self._loop.stop()
        if exc:
            log.error(str(exc))
            raise exc

    def start(self, host='localhost', port=PORT, password=None, certificate=None, debug=False):
        """Start the :class:`Service`.

        Parameters
        ----------
        host : :obj:`str`, optional
            The hostname of the Network :class:`~msl.network.manager.Manager` that the
            :class:`Service` should connect to.
        port : :obj:`int`, optional
            The port number of the Network :class:`~msl.network.manager.Manager` that
            the :class:`Service` should connect to.
        password : :obj:`str`, optional
            The password that is required to connect to the Network
            :class:`~msl.network.manager.Manager`. If not specified then you will
            be asked for the password (only if the Network :class:`~msl.network.manager.Manager`
            requires a password to be able to connect to it).
        certificate : :obj:`str`, optional
            The path to the certificate file to use for the TLS connection
            with the Network :class:`~msl.network.manager.Manager`.
        debug : :obj:`bool`, optional
            Whether to log debug messages for the :class:`Service`.
        """
        self._debug = debug
        self._password = password
        self._address_manager = f'{host}:{port}'

        context = get_ssl_context(host, port, certificate)
        if not context:
            return

        self._loop = asyncio.get_event_loop()

        # self._loop.set_debug(debug)

        self._loop.run_until_complete(
            self._loop.create_connection(
                lambda: self,
                host=host,
                port=port,
                ssl=context,
            )
        )

        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            log.info('CTRL+C keyboard interrupt received')
        finally:
            log.info(f'{self} disconnected')
            self._loop.close()
