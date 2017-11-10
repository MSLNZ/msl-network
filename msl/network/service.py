"""
Base class for all Services.
"""
import json
import asyncio
import inspect
import logging
import getpass
import platform

from .network import Network
from .utils import localhost_aliases
from .constants import PORT, HOSTNAME
from .cryptography import get_ssl_context

log = logging.getLogger(__name__)

IGNORE_ITEMS = ['port', 'address_manager', 'username', 'name', 'start', 'password']
IGNORE_ITEMS += dir(Network) + dir(asyncio.Protocol)


class Service(Network, asyncio.Protocol):

    name = None
    """:obj:`str`: The name of the Service as it will appear on the Network :class:`~msl.network.manager.Manager`."""

    def __init__(self):
        """Base class for all Services."""
        self._loop = None
        self._username = None
        self._password_username = None
        self._password_manager = None
        self._transport = None
        self._identity = dict()
        self._debug = None
        self._port = None
        self._address_manager = None
        if self.name is None:
            self.name = self.__class__.__name__
        self._network_name = self.name

    @property
    def port(self):
        """:obj:`int`: The port number on ``localhost`` that is being used for the
        connection to the Network :class:`~msl.network.manager.Manager`."""
        return self._port

    @property
    def address_manager(self):
        """:obj:`str`: The address of the Network :class:`~msl.network.manager.Manager`
        that this :class:`Service` is connected to."""
        return self._address_manager

    def __repr__(self):
        return '<{} at {:#x} manager={} port={}>'.format(self.name, id(self), self._address_manager, self._port)

    def password(self, name):
        """:obj:`str`: Returns the password to use to try to connect to the Network
        :class:`~msl.network.manager.Manager` at `name`."""
        if self._identity:
            # once the Service sends its identity to the Manager any subsequent password requests
            # can only be from a Client that is linked with the Service and therefore something
            # peculiar is happening because a Client never needs to know a password from a Service.
            # Without this self._identity check a Client could potentially retrieve the password
            # of a user in plain-text format. Also, if the getpass function is called it is a
            # blocking function and therefore the Service blocks all other requests until getpass returns
            return 'You do not have permission to receive the password'
        if name == self._address_manager and self._password_manager is not None:
            return self._password_manager
        elif self._password_username is not None:
            return self._password_username
        else:
            return getpass.getpass(f'Enter the password for {name} > ')

    def username(self, name):
        """:obj:`str`: The username to use to connect to the Network
        :class:`~msl.network.manager.Manager` at `name`."""
        if self._identity:
            # see the comment in the password() method why we do this self._identity check
            return 'You do not have permission to receive the username'
        if self._username is None:
            return input(f'Enter the username for {name} > ')
        return self._username

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
                except TypeError:  # then the attribute is not a callable object
                    value = attrib
                self._identity['attributes'][item] = value
        return self._identity

    def connection_made(self, transport):
        """Automatically called when the connection to the Network
        :class:`~msl.network.manager.Manager` has been established."""
        self._transport = transport
        self._port = int(transport.get_extra_info('sockname')[1])
        self._network_name = '{}[{}]'.format(self.name, self._port)
        log.info(f'{self} connection made')

    def data_received(self, data):
        """New data is received for the :class:`Service`.

        .. _JSON: http://www.json.org/

        Parameters
        ----------
        data : :obj:`bytes`
            A :class:`Service` receives data that will be converted into a JSON_ object.
            The input data **MUST** have one of the following formats.

            If the input data represents an error from the Network
            :class:`~msl.network.manager.Manager` then the JSON_ object will be::

                {
                    'error' : boolean (True)
                    'message': string (a short description of the error message)
                    'traceback': list of strings (a detailed stack trace of the error)
                    'return': null
                    'requester': string (the hostname:port of the Manager)
                }

            If the input data represents a request from a :class:`~msl.network.client.Client`
            then the JSON_ object must contain::

                {
                    'requester': string (the address of the device that made the request)
                    'attribute': string (the name of a method or variable to access from the Service)
                    'parameters': object (key-value pairs to be passed to the Service's method)
                    'error' : boolean (False)
                }

        Returns
        -------
        :obj:`bytes`
            The reply from the :class:`Service`.

            A :class:`Service` will reply with a JSON_ object in one of the following formats.

            If the :class:`Service` raised an exception then the JSON_ object must contain::

                {
                    'error' : boolean (True)
                    'message': string (a short description of the error)
                    'traceback': list of strings (a detailed stack trace of the error)
                    'return': null
                    'requester': string (the address of the device that made the request)
                }

            If the :class:`Service` successfully executed the request then the JSON_ object
            must contain::

                {
                    'return': object (whatever the reply is from the Service)
                    'requester': string (the address of the device that made the request)
                    'error' : boolean (False)
                }

        """
        if self._debug:
            log.debug(f'{self._network_name} received {data}')

        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            log.error(f'{self._network_name} {e.__class__.__name__}: {e}')
            self.send_error(self._transport, e, None)
            return

        if data['error']:
            # Then log the error message and don't send a reply back to the Manager.
            # Ideally, the Manager is the only device that would send an error to the
            # Service, which could happen during the handshake if the password or identity
            # that the Service provided was invalid.
            try:
                msg = '\n'.join(data['traceback'])  # traceback should be a list of strings
            except TypeError:
                msg = data.get('message', 'Error: Unfortunately, no error message has been provided')
            log.error(f'{self._network_name} {msg}')
            return

        try:
            attrib = getattr(self, data['attribute'])
        except Exception as e:
            log.error(f'{self._network_name} {e.__class__.__name__}: {e}')
            self.send_error(self._transport, e, requester=data['requester'])
            return

        if callable(attrib):
            try:
                reply = attrib(**data['parameters'])
            except Exception as e:
                log.error(f'{self._network_name} {e.__class__.__name__}: {e}')
                self.send_error(self._transport, e, requester=data['requester'])
                return
        else:
            reply = attrib

        self.send_reply(self._transport, reply, requester=data['requester'])

    def connection_lost(self, exc):
        """Automatically called when the connection to the
        Network :class:`~msl.network.manager.Manager` has been closed."""
        log.info(f'{self} connection lost')
        self._transport = None
        self._port = None
        self._address_manager = None
        self._loop.stop()
        if exc:
            log.error(str(exc))
            raise exc

    def start(self, host='localhost', port=PORT, username=None, password_username=None,
              password_manager=None, certificate=None, debug=False):
        """Start the :class:`Service`.

        Parameters
        ----------
        host : :obj:`str`, optional
            The hostname of the Network :class:`~msl.network.manager.Manager` that the
            :class:`Service` should connect to.
        port : :obj:`int`, optional
            The port number of the Network :class:`~msl.network.manager.Manager` that
            the :class:`Service` should connect to.
        username : :obj:`str`, optional
            The username to use to connect to Network :class:`~msl.network.manager.Manager`.
            If not specified then you will be asked for the username (only if the Network
            :class:`~msl.network.manager.Manager` requires login credentials to be able
            to connect to it).
        password_username : :obj:`str`, optional
            The password that is associated with `username`. Can be specified if the Network
            :class:`~msl.network.manager.Manager` requires a login to connect to it. If the
            `password_username` value is not specified then you will be asked for the
            password if needed.
        password_manager : :obj:`str`, optional
            The password of the Network :class:`~msl.network.manager.Manager`. A Network
            :class:`~msl.network.manager.Manager` can be started with the option to
            set a global password required which all connecting devices must enter in order
            to connect to it. If the `password_manager` value is not specified then you will
            be asked for the password if needed.
        certificate : :obj:`str`, optional
            The path to the certificate file to use for the TLS connection
            with the Network :class:`~msl.network.manager.Manager`.
        debug : :obj:`bool`, optional
            Whether to log debug messages for the :class:`Service`.
        """
        if host in localhost_aliases():
            host = HOSTNAME
            self._address_manager = f'localhost:{port}'
        else:
            self._address_manager = f'{host}:{port}'

        self._debug = debug
        self._username = username
        self._password_username = password_username
        self._password_manager = password_manager

        context = get_ssl_context(host=host, port=port, certificate=certificate)
        if not context:
            return
        context.check_hostname = host != HOSTNAME

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

        # https://stackoverflow.com/questions/27480967/why-does-the-asyncios-event-loop-suppress-the-keyboardinterrupt-on-windows
        async def wakeup():
            while True:
                await asyncio.sleep(1)
        asyncio.async(wakeup())

        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            log.info('CTRL+C keyboard interrupt received')
        finally:
            log.info(f'{self} disconnected')
            self._loop.close()
