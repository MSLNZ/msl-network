"""
Use the :func:`connect` function to connect to a Network
:class:`~msl.network.manager.Manager` as a :class:`Client`.
"""
import asyncio
import platform
import threading
import uuid
from concurrent.futures import Future
from time import perf_counter
from time import sleep

from .constants import DISCONNECT_REQUEST
from .constants import NOTIFICATION_UID
from .constants import PORT
from .constants import SHUTDOWN_MANAGER
from .constants import SHUTDOWN_SERVICE
from .json import deserialize
from .network import Device
from .service import filter_service_start_kwargs
from .utils import logger


def connect(*, name='Client', host='localhost', port=PORT, timeout=10,
            username=None, password=None, password_manager=None,
            read_limit=None, disable_tls=False, cert_file=None,
            assert_hostname=True, auto_save=False):
    """Create a new connection to a Network :class:`~msl.network.manager.Manager`
    as a :class:`Client`.

    .. versionchanged:: 0.4
       Renamed `certificate` to `certfile`.

    .. versionchanged:: 1.0
       Renamed `certfile` to `cert_file`.
       Added the `auto_save` and `read_limit` keyword arguments.

    Parameters
    ----------
    name : :class:`str`, optional
        A name to assign to the :class:`Client` to help identify it on the
        network.
    host : :class:`str`, optional
        The hostname (or IP address) of the Network
        :class:`~msl.network.manager.Manager` that the
        :class:`~msl.network.client.Client` should connect to.
    port : :class:`int`, optional
        The port number of the Network :class:`~msl.network.manager.Manager`
        that the :class:`~msl.network.client.Client` should connect to.
    timeout : :class:`float`, optional
        The maximum number of seconds to wait to connect to the Network
        :class:`~msl.network.manager.Manager`.
    username : :class:`str`, optional
        The username to use to connect to the Network
        :class:`~msl.network.manager.Manager`. You need to specify a username
        to connect to a :class:`~msl.network.manager.Manager` only if the
        :class:`~msl.network.manager.Manager` was started using the
        ``--auth-login`` flag. If a username is required, and you have not
        specified a value then you will be asked for a username. See
        :mod:`~msl.network.cli_start` for more details.
    password : :class:`str`, optional
        The password that is associated with `username`. If a password is
        required, and you have not specified a value then you will be asked
        for the password.
    password_manager : :class:`str`, optional
        The password that is associated with the Network
        :class:`~msl.network.manager.Manager`. You need to specify the password
        only if the Network :class:`~msl.network.manager.Manager` was started
        using the ``--auth-password`` flag. If a password is required, and you
        have not specified a value then you will be asked for the password.
    read_limit : :class:`int`, optional
        The buffer size limit when reading bytes from a network stream.
        If :data:`None` then there is no (practical) limit.
    disable_tls : :class:`bool`, optional
        Whether to connect to the Network :class:`~msl.network.manager.Manager`
        with or without using the secure TLS protocol.
    cert_file : :class:`str`, optional
        The path to a certificate file to use for the secure TLS connection
        with the Network :class:`~msl.network.manager.Manager`.
        Not used if `disable_tls` is :data:`True`.
    assert_hostname : :class:`bool`, optional
        Whether to check that the hostname of the Network
        :class:`~msl.network.manager.Manager` matches the value of `host`.
        Not used if `disable_tls` is :data:`True`.
    auto_save : :class:`bool`, optional
        Whether to automatically save the certificate of the Network
        :class:`~msl.network.manager.Manager` if the certificate is not
        already saved. Not used if `disable_tls` is :data:`True`.

    Returns
    -------
    :class:`Client`
        A new connection to a Network :class:`~msl.network.manager.Manager`.
    """
    kwargs = locals()
    client = Client(name)
    client._start(**kwargs)  # noqa
    return client


def filter_client_connect_kwargs(**kwargs):
    """From the specified keyword arguments only return those that are valid
    for :func:`.connect`.

    .. versionadded:: 0.4

    Parameters
    ----------
    kwargs
        All keyword arguments that are not in the function signature of
        :func:`.connect` are silently ignored and are not included in
        the output.

    Returns
    -------
    :class:`dict`
        Valid keyword arguments that can be passed to :func:`.connect`.
    """
    # a Client uses the same keyword arguments to connect to a Manager
    # as a Service does, so we can use the same parser function
    return filter_service_start_kwargs(**kwargs)


class Client(Device):

    def __init__(self, name):
        """Base class for all Clients.

        .. attention::
            Do not instantiate directly. Use :meth:`connect` to connect to
            a Network :class:`~msl.network.manager.Manager`.
        """
        super(Client, self).__init__(name)
        self._connected = False
        self._futures = {}
        self._identity = {
            'type': 'client',
            'name': self._name,
            'language': f'Python {platform.python_version()}',
            'os': f'{platform.system()} {platform.release()} {platform.machine()}'
        }
        self._links = []
        self._start_kwargs = {}

    def __del__(self):
        self.disconnect()

    def __repr__(self):
        if self._connected:
            return f'<{self._name} manager={self._address_manager} ' \
                   f'port={self._port}>'
        else:
            return f'<{self._name} disconnected>'

    def admin_request(self, attrib, *args, **kwargs):
        """Send a request to the Network :class:`~msl.network.manager.Manager`
        as an administrator.

        The user that calls this method must have administrative privileges
        for that :class:`~msl.network.manager.Manager`. See
        :mod:`~msl.network.cli_user` for details on how to create a user
        that is an administrator .

        .. versionchanged:: 0.3
           Added a `timeout` option as one of the keyword arguments.

        Parameters
        ----------
        attrib : :class:`str`
            The attribute of the :class:`~msl.network.manager.Manager`.
            Can contain dots ``.`` to access sub-attributes.
        *args
            The arguments to send to `attrib` of the
            :class:`~msl.network.manager.Manager`.
        **kwargs
            The keyword arguments to send to `attrib` of the
            :class:`~msl.network.manager.Manager`. Also accepts a `timeout`
            keyword argument as a :class:`float` or :class:`int` as the
            maximum number of seconds to wait for the reply from the Network
            :class:`~msl.network.manager.Manager`. The default timeout is
            :data:`None`.

        Returns
        -------
        The reply from the Network :class:`~msl.network.manager.Manager`.

        Examples
        --------
        .. invisible-code-block: pycon

           >>> import conftest
           >>> from msl.network.database import UsersTable
           >>> manager = conftest.Manager()
           >>> ut = UsersTable(database=manager.database)
           >>> ut.insert('Alice', 'alice', False)
           >>> ut.insert('Bob', 'bob', False)
           >>> ut.insert('Charlie', 'charlie', False)
           >>> ut.insert('Eve', 'eve', False)
           >>> ut.close()
           >>> kwargs = manager.kwargs  # noqa

        >>> from msl.network import connect
        >>> cxn = connect(**kwargs)
        >>> cxn.admin_request('users_table.usernames')
        ['Alice', 'Bob', 'Charlie', 'Eve', 'admin']
        >>> cxn.admin_request('users_table.is_user_registered', 'N.Bohr')
        False

        An admin can also shut down the :class:`~msl.network.manager.Manager`

        >>> from msl.network.constants import SHUTDOWN_MANAGER
        >>> cxn.admin_request(SHUTDOWN_MANAGER)

        .. invisible-code-block: pycon

           >>> manager.remove_files()

        """
        if 'asynchronous' in kwargs:
            raise ValueError('Cannot make asynchronous requests to a Manager')
        return self._new_request('Manager', attrib, *args, **kwargs)

    def disconnect(self, timeout=None):
        """Disconnect from the Network :class:`~msl.network.manager.Manager`.

        .. versionchanged:: 1.0
           Added the `timeout` keyword argument.

        Parameters
        ----------
        timeout : :class:`int` or :class:`float`, optional
            The maximum number of seconds to wait for the reply from the
            Network :class:`~msl.network.manager.Manager`.
        """
        if not self._connected:
            return

        logger.debug('disconnect requested')
        self._new_request(
            self._network_name,
            DISCONNECT_REQUEST,
            timeout=timeout,
        )

    def is_connected(self):
        """Whether the :class:`.Client` is currently connected to the
        Network :class:`~msl.network.manager.Manager`.

        .. versionadded:: 1.0

        Returns
        -------
        :class:`bool`
            Whether the connection is active.
        """
        return self._connected

    def link(self, service, *, timeout=None):
        """Link with a :class:`~msl.network.service.Service` on the Network
        :class:`~msl.network.manager.Manager`.

        .. versionchanged:: 0.3
           Added the `timeout` keyword argument.

        Parameters
        ----------
        service : :class:`str`
            The name of the :class:`~msl.network.service.Service` to link with.
        timeout : :class:`int` or :class:`float`, optional
            The maximum number of seconds to wait for the reply from the
            Network :class:`~msl.network.manager.Manager`.

        Returns
        -------
        :class:`~msl.network.client.Link`
            A :class:`~msl.network.client.Link` with the requested `service`.
        """
        logger.debug('linking with %r', service)
        identity = self._new_request('Manager', 'link', service, timeout=timeout)
        link = Link(self, service, identity)
        self._links.append(link)
        return link

    def identities(self, *, as_string=False, indent=2, timeout=None):
        """Returns the identities of all devices that are connected to the
        Network :class:`~msl.network.manager.Manager`.

        .. versionchanged:: 0.3
           Added the `timeout` keyword argument.

        .. versionchanged:: 0.4
           Renamed `as_yaml` to `as_string`.

        .. versionchanged:: 1.0
           Renamed this method from `manager` to `identities`.

        Parameters
        ----------
        as_string : :class:`bool`, optional
            Whether to return the information from the Network
            :class:`~msl.network.manager.Manager` as a *human-readable* string.
        indent : :class:`int`, optional
            The amount of indentation added for each recursive level. Only used if
            `as_string` is :data:`True`.
        timeout : :class:`int` or :class:`float`, optional
            The maximum number of seconds to wait for the reply from the
            Network :class:`~msl.network.manager.Manager`.

        Returns
        -------
        :class:`dict` or :class:`str`
            The identities of all connected devices.
        """
        identity = self._new_request('Manager', 'identity', timeout=timeout)
        if not as_string:
            return identity
        space = ' ' * indent
        s = [f'Manager[{identity["hostname"]}:{identity["port"]}]']
        for key in sorted(identity):
            if key in ('clients', 'services', 'hostname', 'port'):
                pass
            elif key == 'attributes':
                s.append(space + 'attributes:')
                for item in sorted(identity[key]):
                    s.append(2 * space + f'{item}{identity[key][item]}')
            else:
                s.append(space + f'{key}: {identity[key]}')
        s.append(f'Clients [{len(identity["clients"])}]:')
        for network_name in sorted(identity['clients']):
            s.append(space + network_name)
            keys = identity['clients'][network_name]
            for key in sorted(keys):
                if key == 'name' or key == 'address':
                    continue
                s.append(2 * space + f'{key}: {keys[key]}')
        s.append(f'Services [{len(identity["services"])}]:')
        for name in sorted(identity['services']):
            s.append(space + f'{name}[{identity["services"][name]["address"]}]')
            service = identity['services'][name]
            for key in sorted(service):
                if key == 'attributes':
                    s.append(2 * space + 'attributes:')
                    for item in sorted(service[key]):
                        signature = service[key][item]
                        if not isinstance(signature, str) or not signature.startswith('('):
                            # then it is a class constant or a property method
                            signature = f'() -> {signature}'
                        s.append(3 * space + f'{item}{signature}')
                elif key == 'address':
                    continue
                else:
                    s.append(2 * space + f'{key}: {service[key]}')
        return '\n'.join(s)

    def spawn(self, name='Client'):
        """Returns a new connection to the Network
        :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        name : :class:`str`, optional
            The name to assign to the new :class:`Client`.

        Returns
        -------
        :class:`Client`:
            A new Client.
        """
        return connect(name=name, **self._start_kwargs)

    def unlink(self, link, *, timeout=None):
        """Unlink from a :class:`~msl.network.service.Service` on the Network
        :class:`~msl.network.manager.Manager`.

        .. versionadded:: 0.5

        Parameters
        ----------
        link : :class:`~msl.network.client.Link`
            The object that is linked with the
            :class:`~msl.network.service.Service`.
        timeout : :class:`int` or :class:`float`, optional
            The maximum number of seconds to wait for the reply from the
            Network :class:`~msl.network.manager.Manager`.
        """
        if not isinstance(link, Link):
            raise TypeError(f'Must pass in a Link object, received {type(link)}')
        logger.debug('preparing to unlink %r', link)
        success = self._new_request('Manager', 'unlink',
                                    link.service_name, timeout=timeout)
        if success:
            self._links.remove(link)

    def _new_request(self, service, attribute, *args, **kwargs):
        # Create a new request to send to a Manager
        if not self._connected:
            raise ConnectionError(
                f'Disconnected from Manager[{self._address_manager}], '
                f'cannot send request to {service!r}'
            )

        asynchronous = kwargs.pop('asynchronous', False)
        timeout = kwargs.pop('timeout', None)
        uid = str(uuid.uuid4())
        request = {
            'args': args,
            'attribute': attribute,
            'error': False,
            'kwargs': kwargs,
            'service': service,
            'uid': uid
        }
        future = Future()
        future.request = f'{service}.{attribute}'
        self._futures[uid] = future
        self._loop.call_soon_threadsafe(self._queue.put_nowait, request)
        if asynchronous:
            return future
        return future.result(timeout=timeout)

    def _run_in_thread(self):
        # Runs the request/response event loop in a separate thread
        asyncio.set_event_loop(self._loop)
        self._tasks.append(self._handle_responses())
        self._tasks.append(self._send_requests())
        self._run_until_complete()

    def _start(self, **kwargs):
        # Start the connection in a separate thread
        self._start_kwargs = {k: v for k, v in kwargs.items() if k != 'name'}

        self._loop = self._create_connection(**kwargs)
        if self._loop is None:
            # then the user chose to not accept the SSL certificate
            raise ConnectionRefusedError('SSL certificate required')

        threading.Thread(
            target=self._run_in_thread,
            name=self._network_name,
            daemon=True
        ).start()

        while not self._connected:
            sleep(0.01)

        return True

    async def _handle_responses(self):
        # Handle responses until EOF
        logger.debug('start response loop (consumer)')
        while True:
            line = await self._reader.readline()
            if not line:
                logger.debug('received EOF')
                self._connected = False
                self._queue.put_nowait(None)
                self.shutdown_handler()
                error = ConnectionAbortedError(
                    f'Manager[{self._address_manager}] closed the connection')
                if not self._futures:
                    raise error
                disconnect = f'{self._network_name}.{DISCONNECT_REQUEST}'
                shutdown = f'Manager.{SHUTDOWN_MANAGER}'
                for future in self._futures.values():
                    if future.request in [disconnect, shutdown]:
                        future.set_result(None)
                    else:
                        future.set_exception(error)
                break

            if len(line) > self._max_debug_length:
                half = self._max_debug_length // 2
                logger.debug('response: %s ... %s', line[:half], line[-half:])
            else:
                logger.debug('response: %s', line)

            # consume response
            response = deserialize(line)
            future = self._futures.pop(response['uid'], None)

            if response['error']:
                message = [f'Manager[{self._address_manager}] returned '
                           f'the following exception:\n']
                if response['traceback']:
                    message.extend(response['traceback'])
                    if response['message'] != response['traceback'][-1]:
                        message.append(response['message'])
                else:
                    message.append(response['message'])
                exception = RuntimeError('\n'.join(message))
                if future is None:
                    # The Manager returned an error after receiving a reply
                    # to a Manager's request. Since an admin_request cannot
                    # be sent asynchronously the last future must be a
                    # request for a Manager
                    _, future = self._futures.popitem()
                    assert future.request.startswith('Manager.')
                future.set_exception(exception)
            elif future is not None:
                future.set_result(response['result'])
            elif response['uid'] == NOTIFICATION_UID:
                # TODO might want to execute this in an Executor
                for link in self._links:
                    if link.service_name == response['service']:
                        args, kwargs = response['result']
                        link.notification_handler(*args, **kwargs)
            elif not response['uid']:
                # if the Manager makes a request (e.g., the username or
                # password when a Client makes an admin request) then
                # the uid is an empty string
                if 'result' in response:
                    _, future = self._futures.popitem()
                    assert future.request.startswith('Manager.')
                    future.set_result(response['result'])
                else:
                    await self._handle_manager_request(response)
            else:
                assert False, 'should not get here'

        logger.debug('finish response loop (consumer)')

    async def _send_requests(self):
        # FIFO queue to send requests to a Manager
        logger.debug('start request loop (producer)')
        self._connected = True
        while True:
            request = await self._queue.get()
            if request is None:
                self._queue.task_done()
                break
            logger.debug('request: %s', request)
            try:
                await self._write(request)  # produce request
            except Exception as e:
                future = self._futures.pop(request['uid'])
                future.set_exception(e)
            finally:
                self._queue.task_done()
        logger.debug('finish request loop (producer)')


class Link(object):

    def __init__(self, client, service, identity):
        """A network link between a :class:`Client` and a
        :class:`~msl.network.service.Service`.

        .. attention::
            Not to be instantiated directly. A :class:`Client` creates a
            :class:`Link` via the :meth:`Client.link` method.
        """
        self._client = client
        self._service_name = service
        self._service_identity = identity
        self._request = client._new_request  # noqa
        logger.debug('linked with %s[%s]', service, identity['address'])

    def acquire_lock(self, shared=False, timeout=None):
        """Acquire a lock with the linked :class:`~msl.network.service.Service`.

        When a lock is acquired, no more :class:`.Client`\\s are allowed to
        link with the :class:`~msl.network.service.Service` until all locks
        have been released.

        .. versionadded:: 1.0

        Parameters
        ----------
        shared : :class:`bool`, optional
            Whether the lock is exclusive or shared. An exclusive lock can only
            be acquired if a single :class:`.Client` is linked with the
            :class:`~msl.network.service.Service`. A shared lock allows for
            multiple simultaneous links, however, once any of the linked
            :class:`.Client`\\s requests a lock the lock is shared amongst the
            currently-linked :class:`.Client`\\s and no new :class:`.Client`\\s
            can link with the :class:`~msl.network.service.Service` until all
            locks have been released.
        timeout : :class:`int` or :class:`float`, optional
            The maximum number of seconds to wait for the reply from the
            Network :class:`~msl.network.manager.Manager`.

        Returns
        -------
        :class:`list` of :class:`str`
            The names of the :class:`.Client`\\s that are linked with the
            :class:`~msl.network.service.Service` while the lock is active.
            For an exclusive lock, only a single link is allowed so the list
            contains a single item that is the name of the :class:`.Client`
            that requested the lock.

        Raises
        ------
        RuntimeError
            If a lock cannot be acquired.
        """
        return self._request('Manager', 'acquire_lock', self._service_name,
                             shared=shared, timeout=timeout)

    def release_lock(self, timeout=None):
        """Release a lock with the linked :class:`~msl.network.service.Service`.

        .. versionadded:: 1.0

        Parameters
        ----------
        timeout : :class:`int` or :class:`float`, optional
            The maximum number of seconds to wait for the reply from the
            Network :class:`~msl.network.manager.Manager`.

        Returns
        -------
        :class:`list` of :class:`str`
            The names of the :class:`.Client`\\s that still have a lock with
            the :class:`~msl.network.service.Service` after this lock has
            been released. An emtpy list means that there are no active locks.
        """
        return self._request('Manager', 'release_lock', self._service_name,
                             timeout=timeout)

    @property
    def service_address(self):
        """:class:`str`: The address of the :class:`~msl.network.service.Service`
        that this object is linked with."""
        return self._service_identity['address']

    @property
    def service_attributes(self):
        """:class:`dict`: The attributes of the :class:`~msl.network.service.Service`
        that this object is linked with."""
        return self._service_identity['attributes']

    @property
    def service_language(self):
        """:class:`str`: The programming language that the
        :class:`~msl.network.service.Service` is running on."""
        return self._service_identity['language']

    @property
    def service_name(self):
        """:class:`str`: The name of the :class:`~msl.network.service.Service`
        that this object is linked with."""
        return self._service_name

    @property
    def service_os(self):
        """:class:`str`: The operating system that the
        :class:`~msl.network.service.Service` is running on."""
        return self._service_identity['os']

    def disconnect(self, timeout=None):
        """An alias for :meth:`unlink`.

        .. versionadded:: 0.5
        """
        self.unlink(timeout=timeout)

    def notification_handler(self, *args, **kwargs):
        """Handle a notification from the :class:`~msl.network.service.Service`
        that emitted a notification.

        .. important::
           You must re-assign this method at the instance level in order to
           handle the notification.

        .. versionadded:: 0.5

        Parameters
        ----------
        args
            The arguments that were emitted.
        kwargs
            The keyword arguments that were emitted.

        Examples
        --------
        .. invisible-code-block: pycon

           >>> import pytest
           >>> pytest.skip('skip notification_handler example')

        The following assumes that the :ref:`heartbeat-service-source` is running
        on the same computer. Using :obj:`types.MethodType` allows for the
        `print_notification` function to access the `self` attribute of `heartbeat`.

        >>> import types
        >>> from msl.network import connect
        >>> cxn = connect()
        >>> heartbeat = cxn.link('Heartbeat')
        >>> def print_notification(self, *args, **kwargs):
        ...     print(f'The {self.service_name} Service emitted', args, kwargs)
        ...
        >>> heartbeat.notification_handler = types.MethodType(print_notification, heartbeat)
        The Heartbeat Service emitted (72,) {}
        The Heartbeat Service emitted (73,) {}
        The Heartbeat Service emitted (74,) {}
        The Heartbeat Service emitted (75,) {}
        The Heartbeat Service emitted (76,) {}
        The Heartbeat Service emitted (77,) {}
        >>> heartbeat.reset()
        The Heartbeat Service emitted (0,) {}
        The Heartbeat Service emitted (1,) {}
        The Heartbeat Service emitted (2,) {}
        The Heartbeat Service emitted (3,) {}
        The Heartbeat Service emitted (4,) {}
        The Heartbeat Service emitted (5,) {}
        The Heartbeat Service emitted (6,) {}
        >>> heartbeat.kill()
        >>> cxn.disconnect()

        See Also
        --------
        :meth:`~msl.network.service.Service.emit_notification`
        :meth:`~msl.network.service.Service.emit_notification_threadsafe`
        """
        pass

    def shutdown_service(self, *args, **kwargs):
        """Send a request for the :class:`~msl.network.service.Service` to
        shut down.

        A :class:`~msl.network.service.Service` must also implement a method
        called ``shutdown_service`` otherwise calling this
        :meth:`shutdown_service` method will raise an exception.

        See :ref:`ssh-example` for an example use case.

        .. versionadded:: 0.5

        Parameters
        ----------
        args
            The positional arguments that are passed to the ``shutdown_service``
            method of the :class:`~msl.network.service.Service` that this object
            is linked with.
        kwargs
            The keyword arguments that are passed to the ``shutdown_service``
            method of the :class:`~msl.network.service.Service` that this object
            is linked with. Also accepts a `timeout` keyword argument as a
            :class:`float` or :class:`int` as the maximum number of seconds to
            wait for the reply from the Network :class:`~msl.network.manager.Manager`.
            The default timeout is :data:`None`.

        Returns
        -------
        Whatever the ``shutdown_service`` method of the :class:`~msl.network.service.Service` returns.
        """
        out = self._request(self._service_name, SHUTDOWN_SERVICE, *args, **kwargs)
        self._client._links.remove(self)  # noqa
        self._client = None
        return out

    def unlink(self, timeout=None):
        """Unlink from the :class:`~msl.network.service.Service` on the Network
        :class:`~msl.network.manager.Manager`.

        .. versionadded:: 0.5

        Parameters
        ----------
        timeout : :class:`int` or :class:`float`, optional
            The maximum number of seconds to wait for the reply from the
            Network :class:`~msl.network.manager.Manager`.
        """
        if self._client is not None:
            self._client.unlink(self, timeout=timeout)
            self._client = None

    def __repr__(self):
        if self._client is None:
            return f'<Un-Linked from {self.service_name}[{self.service_address}]>'
        else:
            return f'<Link with {self.service_name}[{self.service_address}] ' \
                   f'at Manager[{self._client._address_manager}]>'  # noqa

    def __getattr__(self, item):
        if self._client is None:
            raise AttributeError(
                f'Cannot access {item!r} since the link has been broken')

        def request(*args, **kwargs):
            return self._request(self._service_name, item, *args, **kwargs)
        return request


class LinkedClient(object):

    def __init__(self, service_name, **kwargs):
        """Create a new :class:`.Client` that has a :class:`.Link` with the
        specified :class:`~msl.network.service.Service`.

        .. versionadded:: 0.4

        Parameters
        ----------
        service_name : :class:`str`
            The name of the :class:`~msl.network.service.Service` to
            :obj:`~msl.network.client.Client.link` with.
        kwargs
            Keyword arguments that are passed to :func:`.connect`.
        """
        # define these before calling super()
        self._client = None
        self._link = None
        super(LinkedClient, self).__init__()
        kwargs.setdefault('name', self.__class__.__name__)
        kwargs.setdefault('timeout', 10)
        self._kwargs = filter_client_connect_kwargs(**kwargs)

        # When starting a Manager and a Service on a remote computer there can
        # be a race condition for the Manager to start, the Service to start and
        # for the Client to link with the Service. We consider the `timeout` kwarg
        # to be the total time to connect to the Manager and link with the Service.
        t0 = perf_counter()
        self._client = connect(**self._kwargs)

        while True:
            if service_name in self._client.identities()['services']:
                break
            if perf_counter() - t0 > self._kwargs['timeout']:
                raise TimeoutError(f'The {service_name!r} service is not available')
            sleep(0.5)

        self._link = self._client.link(service_name)
        self._address_manager = self._client.address_manager
        self._name = self._client.name
        self._port = self._client.port
        self._service_address = self._link.service_address
        self._service_attributes = self._link.service_attributes
        self._service_language = self._link.service_language
        self._service_name = self._link.service_name
        self._service_os = self._link.service_os

    def acquire_lock(self, shared=False, timeout=None):
        """See :obj:`.Link.acquire_lock` for more details."""
        self._check_link('acquire_lock')
        return self._link.acquire_lock(shared=shared, timeout=timeout)

    def admin_request(self, attrib, *args, **kwargs):
        """See :obj:`.Client.admin_request` for more details."""
        self._check_client()
        return self._client.admin_request(attrib, *args, **kwargs)

    def disconnect(self, timeout=None):
        """See :obj:`.Client.disconnect` for more details."""
        if self._client is not None:
            self._client.disconnect(timeout=timeout)
            self._client = None
            self._link = None

    def identity(self):
        """See :obj:`~msl.network.network.Network.identity` for more details."""
        self._check_client()
        return self._client.identity()

    def identities(self, *, as_string=False, indent=2, timeout=None):
        """See :obj:`.Client.identities` for more details."""
        self._check_client()
        return self._client.identities(as_string=as_string, indent=indent, timeout=timeout)

    def is_connected(self):
        """See :obj:`.Client.is_connected` for more details."""
        self._check_client()
        return self._client.is_connected()

    def notification_handler(self, *args, **kwargs):
        """See :obj:`.Link.notification_handler` for more details."""
        # This method is implemented so that is appears in the documentation.
        # The __setattr__ method is what actually gets called when
        # LinkedClient.notification_handler gets re-assigned in the users code.
        pass

    def service_error_handler(self):
        """This method is called immediately before an exception is raised if there
        was an error processing a request on the :class:`~msl.network.service.Service`
        that this object is linked with.

        You can override this method to perform any necessary cleanup (e.g., closing
        file handles, shutting down threads, disconnecting from devices, etc.) before
        a :exc:`RuntimeError` is raised.

        The :class:`~msl.network.service.Service` remains running. This is to
        clean up the :class:`.Client` instance.
        """
        pass

    def shutdown_service(self, *args, **kwargs):
        """See :obj:`.Link.shutdown_service` for more details."""
        self._check_link('shutdown_service')
        self._link.shutdown_service(*args, **kwargs)

    def spawn(self, name='LinkedClient'):
        """Returns a new connection to the Network :class:`~msl.network.manager.Manager`
        that has a :class:`.Link` with the same :class:`~msl.network.service.Service`.

        Parameters
        ----------
        name : :class:`str`, optional
            The name to assign to the new :class:`.Client`.

        Returns
        -------
        :class:`.LinkedClient`:
            A new :class:`.Client` that has a :class:`.Link` with the same
            :class:`~msl.network.service.Service`.
        """
        kwargs = self._kwargs.copy()
        kwargs['name'] = name
        return LinkedClient(self.service_name, **kwargs)

    def unlink(self, timeout=None):
        """See :obj:`.Link.unlink` for more details."""
        if self._link is not None:
            self._link.unlink(timeout=timeout)
            self._link = None

    @property
    def address_manager(self):
        """See :obj:`~msl.network.network.Device.address_manager` for more details."""
        return self._address_manager

    @property
    def client(self):
        """:class:`Client`: The :class:`Client` that is providing the :class:`Link`.

        .. versionadded:: 0.5
        """
        return self._client

    @property
    def link(self):
        """:class:`.Link`: The :class:`.Link` with the :class:`~msl.network.service.Service`."""
        return self._link

    @property
    def name(self):
        """See :obj:`~msl.network.network.Device.name` for more details."""
        return self._name

    @property
    def port(self):
        """See :obj:`~msl.network.network.Device.name` for more details."""
        return self._port

    def release_lock(self, timeout=None):
        """See :obj:`.Link.release_lock` for more details."""
        self._check_link('release_lock')
        return self._link.release_lock(timeout=timeout)

    @property
    def service_address(self):
        """See :obj:`.Link.service_address` for more details."""
        return self._service_address

    @property
    def service_attributes(self):
        """See :obj:`.Link.service_attributes` for more details."""
        return self._service_attributes

    @property
    def service_language(self):
        """See :obj:`.Link.service_language` for more details."""
        return self._service_language

    @property
    def service_name(self):
        """See :obj:`.Link.service_name` for more details."""
        return self._service_name

    @property
    def service_os(self):
        """See :obj:`.Link.service_os` for more details."""
        return self._service_os

    def __repr__(self):
        if self._link is None:
            return f'<Un-Linked[name={self._name}] from ' \
                   f'{self._service_name}[{self._service_address}]>'
        else:
            return f'<Link[name={self._name}] with ' \
                   f'{self._service_name}[{self._service_address}] at ' \
                   f'Manager[{self._address_manager}]>'

    def __setattr__(self, name, value):
        # the notification_handler is a special attribute that must be
        # directly set to self._link
        if name == 'notification_handler':
            self._link.notification_handler = value
        else:
            super(LinkedClient, self).__setattr__(name, value)

    def __getattr__(self, item):
        # all other methods that are called get sent to the Link object
        self._check_link(item)

        def request(*args, **kwargs):
            try:
                return getattr(self._link, item)(*args, **kwargs)
            except:  # noqa
                self.service_error_handler()
                raise
        return request

    def __del__(self):
        self.disconnect()

    def _check_link(self, item):
        if self._link is None:
            raise AttributeError(
                f'Cannot access {item!r} since the link has been broken')

    def _check_client(self):
        if self._client is None:
            raise ConnectionError('The LinkedClient has been disconnected')
