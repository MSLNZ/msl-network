"""
Base class for all Services.
"""
import os
import asyncio
import inspect
import logging
import getpass
import platform
from time import (
    perf_counter,
    sleep,
)
from concurrent.futures import ThreadPoolExecutor

from .network import Network
from .utils import (
    localhost_aliases,
    new_selector_event_loop,
)
from .json import (
    deserialize,
    serialize,
)
from .constants import (
    PORT,
    HOSTNAME,
    IS_WINDOWS,
    DISCONNECT_REQUEST,
    NOTIFICATION_UUID,
    SHUTDOWN_SERVICE,
)

log = logging.getLogger(__name__)

_ignore_attribs = ['port', 'address_manager', 'username', 'start', 'password',
                   'set_debug', 'max_clients', 'ignore_attributes', 'emit_notification']
_ignore_attribs += list(a for a in dir(Network) + dir(asyncio.Protocol) if not a.startswith('_'))


class Service(Network, asyncio.Protocol):

    def __init__(self, *, name=None, max_clients=None, ignore_attributes=None):
        """Base class for all Services.

        .. versionadded:: 0.4
            The `name` and `max_clients` keyword argument.

        .. versionadded:: 0.5
            The `ignore_attributes` keyword argument.

        Parameters
        ----------
        name : :class:`str`, optional
            The name of the Service as it will appear on the Network :class:`~msl.network.manager.Manager`.
            If not specified then uses the class name.
        max_clients : :class:`int`, optional
            The maximum number of :class:`~msl.network.client.Client`\\s that can be linked
            with this :class:`Service`. A value :math:`\\leq` 0 or :data:`None` means that
            there is no limit.
        ignore_attributes : :class:`list` of :class:`str`, optional
            The names of the attributes to not include in the
            :obj:`~msl.network.network.Network.identity` of the :class:`Service`.
            See :meth:`.ignore_attributes` for more details.
        """
        Network.__init__(self)
        asyncio.Protocol.__init__(self)
        self._username = None
        self._password = None
        self._transport = None
        self._identity = dict()
        self._port = None
        self._address_manager = None
        self._name = self.__class__.__name__ if name is None else name
        if max_clients is None or max_clients <= 0:
            self._max_clients = -1
        else:
            self._max_clients = int(max_clients)
        self._buffer = bytearray()
        self._t0 = None  # used for profiling sections of the code
        self._futures = dict()
        self._ignore_attribs = _ignore_attribs.copy()
        if ignore_attributes:
            self.ignore_attributes(ignore_attributes)

    @property
    def address_manager(self):
        """:class:`str`: The address of the Network :class:`~msl.network.manager.Manager`
        that this :class:`Service` is connected to."""
        return self._address_manager

    @property
    def max_clients(self):
        """:class:`int`: The maximum number of :class:`~msl.network.client.Client`\\s
        that can be linked with this :class:`Service`. A value :math:`\\leq` 0 means an
        infinite number of :class:`~msl.network.client.Client`\\s can be linked."""
        return self._max_clients

    @property
    def port(self):
        """:class:`int`: The port number on ``localhost`` that is being used for the
        connection to the Network :class:`~msl.network.manager.Manager`."""
        return self._port

    def emit_notification(self, *args, **kwargs):
        """Emit a notification to all :class:`~msl.network.client.Client`\'s that are
        :class:`~msl.network.client.Link`\\ed with this :class:`Service`.

        .. versionadded:: 0.5

        Parameters
        ----------
        args
            The arguments to emit.
        kwargs
            The keyword arguments to emit.

        See Also
        --------
        :meth:`~msl.network.client.Link.notification_handler`
        """
        # the Network.send_line method also checks if the `writer` is None, but,
        # there is no need to json-serialize [args, kwargs] if self._transport is None
        if self._transport is None:
            return
        self.send_data(self._transport, {'result': [args, kwargs], 'service': self._name,
                                         'uuid': NOTIFICATION_UUID, 'error': False})

    def ignore_attributes(self, names):
        """Ignore attributes from being added to the :obj:`~msl.network.network.Network.identity`
        of the :class:`Service`.

        The are a few reasons why you may want to call this method:

        * If you see warnings that an object is not JSON serializable or that the signature
          of an attribute cannot be found when starting the :class:`Service` and you
          prefer not to see the warnings.
        * If you do not want an attribute to be made publicly known that it exists. However,
          a :class:`~msl.network.client.Client` can still access the ignored attributes.

        Private attributes (i.e., attributes that start with an underscore) are automatically
        ignored and cannot be accessed from a :class:`~msl.network.client.Client` on the network.

        If you want to ignore any attributes then you must call :meth:`.ignore_attributes`
        before calling :meth:`.start`.

        .. versionadded:: 0.5

        Parameters
        ----------
        names : :class:`list` of :class:`str`
            The names of the attributes to not include in the
            :obj:`~msl.network.network.Network.identity` of the :class:`Service`.
        """
        self._ignore_attribs.extend(names)

    def set_debug(self, boolean):
        """Set the debug mode of the :class:`Service`.

        Parameters
        ----------
        boolean : :class:`bool`
            Whether to enable or disable :py:ref:`DEBUG <levels>` logging messages.
        """
        self._debug = bool(boolean)

    def start(self, *, host='localhost', port=PORT, timeout=10, username=None, password=None,
              password_manager=None, certfile=None, disable_tls=False, assert_hostname=True, debug=False):
        """Start the :class:`Service`.

        .. versionchanged:: 0.4
           Renamed `certificate` to `certfile`.

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
        certfile : :class:`str`, optional
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
        self._address_manager = '{}:{}'.format(host, port)

        self._debug = bool(debug)
        self._username = username

        if password and password_manager:
            raise ValueError('Specify either "password" or "password_manager" but not both.\n'
                             'A Manager cannot be started using multiple authentication methods.')
        self._password = password or password_manager

        self._loop = new_selector_event_loop()

        if not self._create_connection(host, port, certfile, disable_tls, assert_hostname, timeout):
            return

        # enable this hack only in DEBUG mode and only on Windows when the SelectorEventLoop is being used
        # See: https://bugs.python.org/issue23057
        if debug and IS_WINDOWS and isinstance(self._loop, asyncio.SelectorEventLoop):
            async def wakeup():
                while True:
                    await asyncio.sleep(1)
            self._loop.create_task(wakeup())

        self._run_forever()

    def connection_lost(self, exc):
        """
        .. attention::
           Do not override this method. It is called automatically when the connection
           to the Network :class:`~msl.network.manager.Manager` has been closed.
        """
        log.info('{!r} connection lost'.format(self._network_name))
        for future in self._futures.values():
            future.cancel()
        self._futures.clear()
        self._transport = None
        self._port = None
        self._address_manager = None
        self._loop.stop()
        if exc:
            log.error(exc)
            raise exc

    def connection_made(self, transport):
        """
        .. attention::
           Do not override this method. It is called automatically when the connection
           to the Network :class:`~msl.network.manager.Manager` has been established.
        """
        self._transport = transport
        self._port = int(transport.get_extra_info('sockname')[1])
        self._network_name = '{}[{}]'.format(self._name, self._port)
        log.info('{!r} connection made'.format(self._network_name))

    def data_received(self, data):
        """
        .. attention::
           Do not override this method. It is called automatically when data is
           received from the Network :class:`~msl.network.manager.Manager`. A
           :class:`Service` will execute a request in a
           :class:`~concurrent.futures.ThreadPoolExecutor`.
        """
        if not self._buffer:
            self._t0 = perf_counter()

        # there is a chunk-size limit of 2**14 for each reply
        # keep reading data on the stream until the TERMINATION bytes are received
        self._buffer.extend(data)
        if not data.endswith(Network.termination):
            return

        dt = perf_counter() - self._t0
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

        attribute = data['attribute']
        # do not allow access to private attributes from the Service
        if attribute.startswith('_'):
            self.send_error(
                self._transport,
                AttributeError('Cannot request a private attribute from {!r}'.format(self._name)),
                requester=data['requester'],
                uuid=data['uuid']
            )
            return

        try:
            attrib = getattr(self, attribute)
        except Exception as e:
            log.error(self._network_name + ' ' + e.__class__.__name__ + ': ' + str(e))
            self.send_error(self._transport, e, requester=data['requester'], uuid=data['uuid'])
            return

        if attribute == SHUTDOWN_SERVICE:
            reply = attrib(*data['args'], **data['kwargs'])
            self.send_reply(self._transport, reply, requester=data['requester'], uuid=data['uuid'])
            for future in self._futures.values():
                while not (future.done() or future.cancelled()):
                    sleep(0.01)
            self.send_data(self._transport, {'service': self._network_name, 'attribute': DISCONNECT_REQUEST})
        elif callable(attrib):
            uid = os.urandom(16)
            executor = ThreadPoolExecutor(max_workers=1)
            self._futures[uid] = self._loop.run_in_executor(executor, self._function, attrib, data, uid)
        else:
            self.send_reply(self._transport, attrib, requester=data['requester'], uuid=data['uuid'])

        log.info('{!r} requested {!r} [{} executing]'.format(data['requester'], data['attribute'], len(self._futures)))

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
                if item.startswith('_') or item in self._ignore_attribs:
                    continue
                attrib = getattr(self, item)
                try:
                    value = str(inspect.signature(attrib))
                except TypeError:  # then the attribute is not a callable object
                    value = attrib
                except ValueError as err:
                    # Cannot get the signature of the callable object.
                    # This can happen if the Service is also a subclass of
                    # some other object, for example a Qt class.
                    log.warning(err)
                    continue
                try:
                    serialize(value)
                except:
                    log.warning('The attribute {!r} is not JSON serializable'.format(item))
                    continue
                self._identity['attributes'][item] = value
        self._identity_successful = True
        return self._identity

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
            return 'You do not have permission to receive the password'
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

    def _function(self, attrib, data, uid):
        try:
            reply = attrib(*data['args'], **data['kwargs'])
            self.send_reply(self._transport, reply, requester=data['requester'], uuid=data['uuid'])
        except Exception as e:
            log.error(self._network_name + ' ' + e.__class__.__name__ + ': ' + str(e))
            self.send_error(self._transport, e, requester=data['requester'], uuid=data['uuid'])
        self._futures.pop(uid, None)


def filter_service_start_kwargs(**kwargs):
    """From the specified keyword arguments only return those that are valid for
    :meth:`~msl.network.service.Service.start`.

    .. versionadded:: 0.4

    Parameters
    ----------
    kwargs
        Keyword arguments. All keyword arguments that are not part of the method
        signature for :meth:`~msl.network.service.Service.start` are silently ignored.

    Returns
    -------
    :class:`dict`
        Valid keyword arguments that can be passed to :meth:`~msl.network.service.Service.start`.
    """
    kws = {}
    for item in inspect.getfullargspec(Service.start).kwonlyargs:
        if item in kwargs:
            kws[item] = kwargs[item]

    # the manager uses an `auth_password` kwarg but a service uses a `password_manager` kwarg
    # however, these kwargs represent the same thing
    if 'auth_password' in kwargs and 'password_manager' not in kws:
        kws['password_manager'] = kwargs['auth_password']

    return kws
