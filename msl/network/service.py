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
from .json import deserialize, serialize
from .utils import localhost_aliases
from .constants import PORT, HOSTNAME, IS_WINDOWS

log = logging.getLogger(__name__)

IGNORE_ITEMS = ['port', 'address_manager', 'username', 'start', 'password', 'set_debug', 'max_clients']
IGNORE_ITEMS += dir(Network) + dir(asyncio.Protocol)

PASSWORD_MESSAGE = 'You do not have permission to receive the password'


class Service(Network, asyncio.Protocol):

    def __init__(self, *, name=None, max_clients=None):
        """Base class for all Services.

        Parameters
        ----------
        name : :class:`str`, optional
            The name of the Service as it will appear on the Network :class:`~msl.network.manager.Manager`.
            If not specified then uses the class name.
        max_clients : :class:`int`, optional
            The maximum number of :class:`~msl.network.client.Client`\'s that can be linked
            with this :class:`Service`. A value <= 0 means that there is no limit.
        """
        self._loop = None
        self._username = None
        self._password = None
        self._transport = None
        self._identity = dict()
        self._debug = False
        self._port = None
        self._address_manager = None
        self._name = self.__class__.__name__ if name is None else name
        if max_clients is None or max_clients <= 0:
            self._max_clients = -1
        else:
            self._max_clients = int(max_clients)
        self._network_name = self._name
        self._buffer = bytearray()
        self._t0 = None  # used for profiling sections of the code
        self._futures = dict()
        self._connection_successful = False

    @property
    def port(self):
        """:class:`int`: The port number on ``localhost`` that is being used for the
        connection to the Network :class:`~msl.network.manager.Manager`."""
        return self._port

    @property
    def address_manager(self):
        """:class:`str`: The address of the Network :class:`~msl.network.manager.Manager`
        that this :class:`Service` is connected to."""
        return self._address_manager

    @property
    def max_clients(self):
        """:class:`int`: The maximum number of :class:`~msl.network.client.Client`\s
        that can be linked with this :class:`Service` (-1 if infinite)."""
        return self._max_clients

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
            return PASSWORD_MESSAGE
        self._connection_successful = True
        if self._password is not None:
            return self._password
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
        self._connection_successful = True
        if self._username is None:
            return input('Enter a username for ' + name + ' > ')
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
            self._identity['name'] = self._name
            self._identity['language'] = 'Python ' + platform.python_version()
            self._identity['os'] = '{} {} {}'.format(platform.system(), platform.release(), platform.machine())
            self._identity['max_clients'] = self._max_clients
            self._identity['attributes'] = dict()
            for item in dir(self):
                if item.startswith('_') or item in IGNORE_ITEMS:
                    continue
                attrib = getattr(self, item)
                try:
                    value = str(inspect.signature(attrib))
                except TypeError:  # then the attribute is not a callable object
                    value = attrib
                try:
                    serialize(value)
                except:
                    log.warning('The attribute "{0}" is not JSON serializable. '
                                'Rename it to be "_{0}" to avoid seeing this message'.format(item))
                    continue
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
        self._network_name = '{}[{}]'.format(self._name, self._port)
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
        # keep reading data on the stream until the TERMINATION bytes are received
        self._buffer.extend(data)
        if not data.endswith(self.TERMINATION):
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
                else:  # in case the 'traceback' key exists but it is an empty list
                    msg = data['message']
            except (TypeError, KeyError):  # in case there is no 'traceback' key
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
            if data['attribute'] == '_password':
                attrib = PASSWORD_MESSAGE
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
        boolean : :class:`bool`
            Whether to enable or disable :py:ref:`DEBUG <levels>` logging messages.
        """
        self._debug = bool(boolean)

    def start(self, *, host='localhost', port=PORT, timeout=10, username=None, password=None,
              password_manager=None, certificate=None, disable_tls=False, assert_hostname=True, debug=False):
        """Start the :class:`Service`.

        Parameters
        ----------
        host : :class:`str`, optional
            The hostname (or IP address) of the Network :class:`~msl.network.manager.Manager`
            that the :class:`Service` should connect to.
        port : :class:`int`, optional
            The port number of the Network :class:`~msl.network.manager.Manager` that
            the :class:`Service` should connect to.
        timeout : :class:`float`, optional
            The maximum number of seconds to wait to establish the connection to the
            :class:`~msl.network.manager.Manager` before raising a :exc:`TimeoutError`.
        username : :class:`str`, optional
            The username to use to connect to the Network :class:`~msl.network.manager.Manager`.
            You need to specify a username only if the Network :class:`~msl.network.manager.Manager`
            was started with the ``--auth-login`` flag. If a username is required and you have not
            specified it when you called this method then you will be asked for a username.
        password : :class:`str`, optional
            The password that is associated with `username`. If a password is required and you
            have not specified it when you called this method then you will be asked for the password.
        password_manager : :class:`str`, optional
            The password that is associated with the Network :class:`~msl.network.manager.Manager`.
            You need to specify the password only if the Network :class:`~msl.network.manager.Manager`
            was started with the ``--auth-password`` flag. If a password is required and you
            have not specified it when you called this method then you will be asked for the password.
        certificate : :class:`str`, optional
            The path to the certificate file to use for the TLS connection
            with the Network :class:`~msl.network.manager.Manager`.
        disable_tls : :class:`bool`, optional
            Whether to connect to the Network :class:`~msl.network.manager.Manager`
            without using the TLS protocol.
        assert_hostname : :class:`bool`, optional
            Whether to force the hostname of the Network :class:`~msl.network.manager.Manager`
            to match the value of `host`.
        debug : :class:`bool`, optional
            Whether to log :py:ref:`DEBUG <levels>` messages for the :class:`Service`.
        """
        if self._transport is not None:
            raise RuntimeError('The Service has already started')

        if host in localhost_aliases():
            host = HOSTNAME
            self._address_manager = 'localhost:{}'.format(port)
        else:
            self._address_manager = '{}:{}'.format(host, port)

        self._debug = bool(debug)
        self._username = username

        if password and password_manager:
            raise ValueError('Specify either "password" or "password_manager" but not both.\n'
                             'A Manager cannot be started using multiple authentication methods.')
        self._password = password or password_manager

        # create a new event loop, rather than using asyncio.get_event_loop()
        # (in case the Service does not run in the threading._MainThread)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        if not self._create_connection(host, port, certificate, disable_tls, assert_hostname, timeout):
            return

        # https://bugs.python.org/issue23057
        # enable this hack only in debug mode and only on Windows
        if debug and IS_WINDOWS:
            async def wakeup():
                while True:
                    await asyncio.sleep(1)
            self._loop.create_task(wakeup())

        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            log.info('CTRL+C keyboard interrupt received')
        finally:
            log.info(str(self) + ' disconnected')
            self._loop.close()
            log.info('closed the event loop')

    @property
    def _identity_successful(self):
        return self._identity

    @property
    def _connection_established(self):
        return self._connection_successful
