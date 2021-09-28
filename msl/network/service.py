"""
Base class for all Services.
"""
import os
import asyncio
import inspect
import getpass
import platform
from time import (
    perf_counter,
    sleep,
)
from concurrent.futures import ThreadPoolExecutor

from .network import Device
from .utils import (
    logger,
    localhost_aliases,
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

_ignore_attribs = [
    'port', 'address_manager', 'username', 'start', 'password',
    'set_debug', 'max_clients', 'ignore_attributes', 'emit_notification'
]
_ignore_attribs += list(a for a in dir(Device) + dir(asyncio.Protocol) if not a.startswith('_'))


class Service(Device, asyncio.Protocol):

    def __init__(self, *, name=None, max_clients=None, ignore_attributes=None):
        """Base class for all Services.

        .. versionadded:: 0.4
            The `name` and `max_clients` keyword argument.

        .. versionadded:: 0.5
            The `ignore_attributes` keyword argument.

        Parameters
        ----------
        name : :class:`str`, optional
            The name of the Service as it will appear on the Network
            :class:`~msl.network.manager.Manager`. If not specified
            then the class name is used. You can also specify the `name`
            in the :meth:`.start` method.
        max_clients : :class:`int`, optional
            The maximum number of :class:`~msl.network.client.Client`\\s
            that can be linked with this :class:`Service`. A value :math:`\\leq` 0
            or :data:`None` means that there is no limit.
        ignore_attributes : :class:`list` of :class:`str`, optional
            The names of the attributes to not include in the
            :obj:`~msl.network.network.Network.identity` of the :class:`Service`.
            See :meth:`.ignore_attributes` for more details.
        """
        Device.__init__(self, name)
        asyncio.Protocol.__init__(self)
        if max_clients is None or max_clients <= 0:
            self._max_clients = -1
        else:
            self._max_clients = int(max_clients)
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
        """Emit a notification to all :class:`~msl.network.client.Client`\\s that are
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

    def start(self, *, name=None, host='localhost', port=PORT, timeout=10,
              username=None, password=None, password_manager=None,
              cert_file=None, disable_tls=False, assert_hostname=True,
              debug=False, auto_save=False):
        """Start the :class:`Service`.

        See :func:`~msl.network.client.connect` for the description
        of each parameter.
        """
        kwargs = {k: v for k, v in locals().items() if k != 'self'}

        if name is not None:
            self._name = name

        if host in localhost_aliases():
            kwargs['host'] = HOSTNAME

        self._address_manager = '{host}:{port}'.format(**kwargs)
        self._debug = bool(debug)
        self._username = username

        if password and password_manager:
            raise ValueError(
                'Specify either "password" or "password_manager" but not both.\n'
                'A Manager cannot be started using multiple authentication methods.'
            )
        self._password = password or password_manager

        self._loop = asyncio.new_event_loop()
        if not self._create_connection(**kwargs):
            return

        # enable this hack only in DEBUG mode and only on Windows when
        # the SelectorEventLoop is used. See: https://bugs.python.org/issue23057
        if self._debug and IS_WINDOWS and isinstance(self._loop, asyncio.SelectorEventLoop):
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
        logger.info('{!r} connection lost'.format(self._network_name))
        for future in self._futures.values():
            future.cancel()
        self._futures.clear()
        self._transport = None
        self._port = None
        self._address_manager = None
        self._loop.stop()
        if exc:
            logger.error(exc)
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
        logger.info('{!r} connection made'.format(self._network_name))

    def data_received(self, data):
        """
        .. attention::
           Do not override this method. It is called automatically when data is
           received from the Network :class:`~msl.network.manager.Manager`. A
           :class:`Service` will execute a request in a
           :class:`~concurrent.futures.ThreadPoolExecutor`.
        """
        message = self._parse_buffer(data)
        if not message:
            return

        dt = perf_counter() - self._t0

        if self._debug:
            n = len(message)
            if dt > 0:
                logger.debug('{} received {} bytes in {:.3g} seconds [{:.3f} MB/s]'.format(
                    self._network_name, n, dt, n*1e-6/dt))
            else:
                logger.debug('{} received {} bytes in {:.3g} seconds'.format(self._network_name, n, dt))
            if len(message) > self._max_print_size:
                logger.debug(message[:self._max_print_size//2] + b' ... ' + message[-self._max_print_size//2:])
            else:
                logger.debug(message)

        try:
            request = deserialize(message)
        except Exception as e:
            logger.error(self._network_name + ' ' + e.__class__.__name__ + ': ' + str(e))
            self.send_error(self._transport, e, None)
            self._check_buffer_for_message()
            return

        if request.get('error', False):
            # Then log the error message and don't send a reply back to the Manager.
            # Ideally, the Manager is the only device that would send an error to the
            # Service, which could happen during the handshake if the password or identity
            # that the Service provided was invalid.
            msg = 'Error: Unfortunately, no error message has been provided'
            try:
                if request['traceback']:
                    msg = '\n'.join(request['traceback'])  # traceback should be a list of strings
                else:  # in case the 'traceback' key exists but it is an empty list
                    msg = request['message']
            except (TypeError, KeyError):  # in case there is no 'traceback' key
                try:
                    msg = request['message']
                except KeyError:
                    pass
            logger.error(self._network_name + ' ' + msg)
            self._check_buffer_for_message()
            return

        attribute = request['attribute']
        # do not allow access to private attributes from the Service
        if attribute.startswith('_'):
            self.send_error(
                self._transport,
                AttributeError('Cannot request a private attribute from {!r}'.format(self._name)),
                requester=request['requester'],
                uuid=request['uuid']
            )
            self._check_buffer_for_message()
            return

        try:
            attrib = getattr(self, attribute)
        except Exception as e:
            logger.error(self._network_name + ' ' + e.__class__.__name__ + ': ' + str(e))
            self.send_error(self._transport, e, requester=request['requester'], uuid=request['uuid'])
            self._check_buffer_for_message()
            return

        if attribute == SHUTDOWN_SERVICE:
            reply = attrib(*request['args'], **request['kwargs'])
            self.send_reply(self._transport, reply, requester=request['requester'], uuid=request['uuid'])
            for future in self._futures.values():
                while not (future.done() or future.cancelled()):
                    sleep(0.01)
            self.send_data(self._transport, {'service': self._network_name, 'attribute': DISCONNECT_REQUEST})
        elif callable(attrib):
            uid = os.urandom(16)
            executor = ThreadPoolExecutor(max_workers=1)
            self._futures[uid] = self._loop.run_in_executor(executor, self._function, attrib, request, uid)
        else:
            self.send_reply(self._transport, attrib, requester=request['requester'], uuid=request['uuid'])

        logger.info('{!r} requested {!r} [{} executing]'.format(
            request['requester'], request['attribute'], len(self._futures)))

        self._check_buffer_for_message()

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
                try:
                    attrib = getattr(self, item)
                except Exception as err:
                    # This can happen if the Service is also a subclass of
                    # another class, for example, the PiCamera class and the other
                    # class defines some of its attributes using the builtin
                    # property function, e.g., property(fget, fset, fdel, doc),
                    # and defines fget=None or if the getattr() function
                    # executes code, like PiCamera.frame does, which raises
                    # a custom exception if the camera is not running.
                    logger.warning('{} [attribute={!r}]'.format(err, item))
                    continue
                try:
                    value = str(inspect.signature(attrib))
                except TypeError:  # then the attribute is not a callable object
                    value = attrib
                except ValueError as err:
                    # Cannot get the signature of the callable object.
                    # This can happen if the Service is also a subclass of
                    # some other object, for example a Qt class.
                    logger.warning(err)
                    continue
                try:
                    serialize(value)
                except:
                    logger.warning('The attribute {!r} is not JSON serializable'.format(item))
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
            logger.error(self._network_name + ' ' + e.__class__.__name__ + ': ' + str(e))
            self.send_error(self._transport, e, requester=data['requester'], uuid=data['uuid'])
        finally:
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
