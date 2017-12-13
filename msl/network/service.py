"""
Base class for all Services.
"""
import os
import time
import asyncio
import inspect
import logging
import getpass
import platform
from concurrent.futures import ThreadPoolExecutor

from .network import Network
from .json import deserialize
from .utils import localhost_aliases
from .constants import PORT, HOSTNAME
from .cryptography import get_ssl_context

log = logging.getLogger(__name__)

IGNORE_ITEMS = ['port', 'address_manager', 'username', 'name', 'start', 'password']
IGNORE_ITEMS += dir(Network) + dir(asyncio.Protocol)


class Service(Network, asyncio.Protocol):

    name = None
    """:obj:`str`: The name of the Service as it will appear on the Network :class:`~msl.network.manager.Manager`."""

    _PASSWORD_MESSAGE = 'You do not have permission to receive the password'

    def __init__(self):
        """Base class for all Services."""
        self._loop = None
        self._username = None
        self._password = None
        self._password_manager = None
        self._transport = None
        self._identity = dict()
        self._debug = False
        self._port = None
        self._address_manager = None
        if self.name is None:
            self.name = self.__class__.__name__
        self._network_name = self.name
        self._buffer = bytearray()
        self._t0 = None  # used for profiling sections of the code
        self._futures = dict()

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
        return '<{} object at {:#x} manager={} port={}>'.format(self.name, id(self), self._address_manager, self._port)

    def password(self, name):
        """
        .. attention::
           Do not override this method. It is called automatically when the Network
           :class:`~msl.network.manager.Manager` requests a password.
        """
        if self._identity:
            # once the Service sends its identity to the Manager any subsequent password requests
            # can only be from a Client that is linked with the Service and therefore something
            # peculiar is happening because a Client never needs to know a password from a Service.
            # Without this self._identity check a Client could potentially retrieve the password
            # of a user in plain-text format. Also, if the getpass function is called it is a
            # blocking function and therefore the Service blocks all other requests until getpass returns
            return Service._PASSWORD_MESSAGE
        if name == self._address_manager and self._password_manager is not None:
            return self._password_manager
        elif self._password is not None:
            return self._password
        else:
            return getpass.getpass('Enter the password for ' + name + ' > ')

    def username(self, name):
        """
        .. attention::
           Do not override this method. It is called automatically when the Network
           :class:`~msl.network.manager.Manager` requests the name of the user.
        """
        if self._identity:
            # see the comment in the password() method why we do this self._identity check
            return 'You do not have permission to receive the username'
        if self._username is None:
            return input('Enter the username for ' + name + ' > ')
        return self._username

    def identity(self):
        """
        .. attention::
           Do not override this method. It is called automatically when the Network
           :class:`~msl.network.manager.Manager` requests the
           :obj:`~msl.network.network.Network.identity` of the :class:`Service`
        """
        if not self._identity:
            self._identity['type'] = 'service'
            self._identity['name'] = self.name
            self._identity['language'] = 'Python ' + platform.python_version()
            self._identity['os'] = '{} {} {}'.format(platform.system(), platform.release(), platform.machine()),
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
        """
        .. attention::
           Do not override this method. It is called automatically when the connection
           to the Network :class:`~msl.network.manager.Manager` has been established.
        """
        self._transport = transport
        self._port = int(transport.get_extra_info('sockname')[1])
        self._network_name = '{}[{}]'.format(self.name, self._port)
        log.info(str(self) + ' connection made')

    def data_received(self, data):
        """
        .. attention::
           Do not override this method. It is called automatically when data is
           received from the Network :class:`~msl.network.manager.Manager`. A
           :class:`Service` will execute a request in a
           :class:`~concurrent.futures.ThreadPoolExecutor`.
        """
        if not self._buffer:
            self._t0 = time.perf_counter()

        # there is a chunk-size limit of 2**14 for each reply
        # keep reading the data on the stream until the \n character is received
        self._buffer.extend(data)
        if not data.endswith(b'\n'):
            return

        dt = time.perf_counter() - self._t0
        buffer_bytes = bytes(self._buffer)
        self._buffer.clear()

        if self._debug:
            n = len(buffer_bytes)
            if dt > 0:
                log.debug('{} received {} bytes in {:.3g} seconds [{:.3f} MB/s]'.format(
                    self._network_name, n, dt, n*1e-6/dt))
            else:
                log.debug('{} received {} bytes in {:.3g} seconds'.format(self._network_name, n, dt))
            if len(buffer_bytes) > self._max_print_size:
                log.debug(buffer_bytes[:self._max_print_size//2] + b' ... ' + buffer_bytes[-self._max_print_size//2:])
            else:
                log.debug(buffer_bytes)

        try:
            data = deserialize(buffer_bytes)
        except Exception as e:
            log.error(self._network_name + ' ' + e.__class__.__name__ + ': ' + str(e))
            self.send_error(self._transport, e, None)
            return

        if data.get('error', False):
            # Then log the error message and don't send a reply back to the Manager.
            # Ideally, the Manager is the only device that would send an error to the
            # Service, which could happen during the handshake if the password or identity
            # that the Service provided was invalid.
            msg = 'Error: Unfortunately, no error message has been provided'
            try:
                if data['traceback']:
                    msg = '\n'.join(data['traceback'])  # traceback should be a list of strings
            except (TypeError, KeyError):
                try:
                    msg = data['message']
                except KeyError:
                    pass
            log.error(self._network_name + ' ' + msg)
            return

        try:
            attrib = getattr(self, data['attribute'])
        except Exception as e:
            log.error(self._network_name + ' ' + e.__class__.__name__ + ': ' + str(e))
            self.send_error(self._transport, e, requester=data['requester'], uuid=data['uuid'])
            return

        if callable(attrib):
            uid = os.urandom(16)
            executor = ThreadPoolExecutor(max_workers=1)
            self._futures[uid] = self._loop.run_in_executor(executor, self._function, attrib, data, uid)
        else:
            if data['attribute'].startswith('_password'):
                attrib = Service._PASSWORD_MESSAGE
            self.send_reply(self._transport, attrib, requester=data['requester'], uuid=data['uuid'])
        log.info(data['requester'] + ' requested ' + data['attribute'] + ' [{} executing]'.format(len(self._futures)))

    def _function(self, attrib, data, uid):
        try:
            reply = attrib(*data['args'], **data['kwargs'])
            self.send_reply(self._transport, reply, requester=data['requester'], uuid=data['uuid'])
        except Exception as e:
            log.error(self._network_name + ' ' + e.__class__.__name__ + ': ' + str(e))
            self.send_error(self._transport, e, requester=data['requester'], uuid=data['uuid'])
        self._futures.pop(uid, None)

    def connection_lost(self, exc):
        """
        .. attention::
           Do not override this method. It is called automatically when the connection
           to the Network :class:`~msl.network.manager.Manager` has been closed.
        """
        log.info(str(self) + ' connection lost')
        self._futures.clear()
        self._transport = None
        self._port = None
        self._address_manager = None
        self._loop.stop()
        if exc:
            log.error(exc)
            raise exc

    def set_debug(self, boolean):
        """Set the debug mode of the :class:`Service`.

        Parameters
        ----------
        boolean : :obj:`bool`
            Whether to enable or disable debug logging messages.
        """
        self._debug = bool(boolean)

    def start(self, *, host='localhost', port=PORT, username=None, password=None,
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
        password : :obj:`str`, optional
            The password that is associated with `username`. If the `password` is not
            specified then you will be asked for the password if needed.
        password_manager : :obj:`str`, optional
            The password of the Network :class:`~msl.network.manager.Manager`. A Network
            :class:`~msl.network.manager.Manager` can be started with the option to
            set a global password which all connecting devices must enter in order
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
            self._address_manager = 'localhost:{}'.format(port)
        else:
            self._address_manager = '{}:{}'.format(host, port)

        self._debug = bool(debug)
        self._username = username
        self._password = password
        self._password_manager = password_manager

        context = get_ssl_context(host=host, port=port, certificate=certificate)
        if not context:
            return
        context.check_hostname = host != HOSTNAME

        # create a new event loop, rather than using asyncio.get_event_loop()
        # (in case the Service does not run in the threading._MainThread)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

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
            log.info(str(self) + ' disconnected')
            self._loop.close()
            log.info('closed the event loop')
