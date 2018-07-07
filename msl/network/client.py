"""
Connect to a Network :class:`~msl.network.manager.Manager`.
"""
import ssl
import time
import uuid
import asyncio
import getpass
import logging
import platform
import threading

from .network import Network
from .json import deserialize
from .utils import localhost_aliases
from .constants import PORT, HOSTNAME
from .cryptography import get_ssl_context
from .exceptions import MSLNetworkError

log = logging.getLogger(__name__)


def connect(*, name='Client', host='localhost', port=PORT, timeout=None, username=None,
            password=None, password_manager=None, certificate=None, disable_tls=False, debug=False):
    """Create a new connection to a Network :class:`~msl.network.manager.Manager`
    as a :class:`Client`.

    Parameters
    ----------
    name : :obj:`str`, optional
        A name to assign to the :class:`Client`.
    host : :obj:`str`, optional
        The hostname of the Network :class:`~msl.network.manager.Manager`
        that the :class:`~msl.network.client.Client` should connect to.
    port : :obj:`int`, optional
        The port number of the Network :class:`~msl.network.manager.Manager`
        that the :class:`~msl.network.client.Client` should connect to.
    timeout : :obj:`float`, optional
        The maximum number of seconds to wait for a reply from the Network
        :class:`~msl.network.manager.Manager` before raising a :exc:`TimeoutError`.
        The default is to wait forever (i.e., no timeout).
    username : :obj:`str`, optional
        The username to use to connect to Network :class:`~msl.network.manager.Manager`.
        If not specified then you will be asked for the `username` when needed.
    password : :obj:`str`, optional
        The password that is associated with `username`. If not specified then you will
        be asked for the password when needed.
    password_manager : :obj:`str`, optional
        The password of the Network :class:`~msl.network.manager.Manager`. A Network
        :class:`~msl.network.manager.Manager` can be started with the option to
        use a global password that is required for all connecting devices to specify
        in order for the device to connect to it. If the `password_manager` value is
        not specified then you will be asked for the password when needed.
    certificate : :obj:`str`, optional
        The path to the certificate file to use for the secure connection
        with the Network :class:`~msl.network.manager.Manager`.
    disable_tls : :obj:`bool`, optional
        Whether to connect to the Network :class:`~msl.network.manager.Manager`
        without using the TLS protocol.
    debug : :obj:`bool`, optional
        Whether to log debug messages for the :class:`Client`.

    Returns
    -------
    :class:`Client`
        A new connection.
    """
    client = Client(name)
    success = client.start(host, port, timeout, username, password,
                           password_manager, certificate, disable_tls, debug)
    if not success:
        client.raise_latest_error()
    return client


class Client(Network, asyncio.Protocol):

    def __init__(self, name):
        """Base class for all Clients.

        .. attention::
            Do not instantiate directly. Use :meth:`connect` to connect to
            a Network :class:`~msl.network.manager.Manager`.
        """
        self._name = name
        self._network_name = name
        self._port = None
        self._loop = None
        self._disable_tls = False
        self._debug = False
        self._username = None
        self._password = None
        self._host_manager = None
        self._port_manager = None
        self._address_manager = None
        self._password_manager = None
        self._transport = None
        self._certificate = None
        self._identity = {
            'type': 'client',
            'name': name,
            'language': 'Python ' + platform.python_version(),
            'os': '{} {} {}'.format(platform.system(), platform.release(), platform.machine())
        }
        self._handshake_finished = False
        self._latest_error = None
        self._buffer = bytearray()
        self._timeout = None
        self._t0 = None  # used for profiling sections of the code
        self._requests = dict()
        self._futures = dict()
        self._pending_requests_sent = False

    @property
    def name(self):
        """:obj:`str`: The name of the :class:`Client` on the Network
        :class:`~msl.network.manager.Manager`."""
        return self._name

    @property
    def port(self):
        """:obj:`int`: The port number on ``localhost`` that is being used for the
        connection to the Network :class:`~msl.network.manager.Manager`."""
        return self._port

    @property
    def address_manager(self):
        """:obj:`str`: The address of the Network :class:`~msl.network.manager.Manager`
        that this :class:`Client` is connected to."""
        return self._address_manager

    @property
    def timeout(self):
        """:obj:`float` or :obj:`None`: The maximum number of seconds to wait for
        a reply from the Network :class:`~msl.network.manager.Manager` before
        raising a :exc:`TimeoutError`."""
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        if value is not None and value < 0:
            raise ValueError('The timeout value cannot be negative')
        self._timeout = value

    def __repr__(self):
        return '<{} object at {:#x} manager={} port={}>'.format(
            self._name, id(self), self._address_manager, self._port)

    def password(self, name):
        """
        .. attention::
           Do not call this method. It is called by the Network
           :class:`~msl.network.manager.Manager` when verifying the login credentials.
        """
        # note that a Service has a special check in its password() method so that a password
        # remains secure, however, a Client does not need this security check because a Client
        # cannot send a request to other Clients
        if name == self._address_manager:
            if self._password_manager is None:
                self._password_manager = getpass.getpass('Enter the password for ' + name + ' > ')
            return self._password_manager
        if self._password is None:
            self._password = getpass.getpass('Enter the password for ' + name + ' > ')
        return self._password

    def username(self, name):
        """
        .. attention::
           Do not call this method. It is called by the Network
           :class:`~msl.network.manager.Manager` when verifying the login credentials.
        """
        # see the comment in the Client.password() method and in the Service.username() method
        if self._username is None:
            self._username = input('Enter the username for ' + name + ' > ')
        return self._username

    def identity(self):
        """:obj:`dict`: Returns the :obj:`~msl.network.network.Network.identity` of the :class:`Client`."""
        return self._identity

    def link(self, service):
        """Link with a :class:`~msl.network.service.Service` on the Network
        :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        service : :obj:`str`
            The name of the :class:`~msl.network.service.Service` to link with.

        Returns
        -------
        :class:`~msl.network.client.Link`
            A :class:`~msl.network.client.Link` with the requested `service`.

        Raises
        ------
        :class:`~msl.network.exceptions.MSLNetworkError`
            If there is no :class:`~msl.network.service.Service` available
            with the name `service`.

        See Also
        --------
        :meth:`send_request`
        """
        if self._debug:
            log.debug('preparing to link with ' + service)
        identity = self._send_request_for_manager('link', service)
        return Link(self, service, identity)

    def disconnect(self):
        """Disconnect from the Network :class:`~msl.network.manager.Manager`."""
        if self._transport is not None:
            uid = self._create_request('self', '__disconnect__')
            self.send_data(self._transport, self._requests[uid])
            self._wait(uid)
            self._clear_all_futures()

    def manager(self, *, as_yaml=False, indent=4):
        """Returns the :obj:`~msl.network.network.Network.identity` of the
        Network :class:`~msl.network.manager.Manager`.

        .. _YAML: https://en.wikipedia.org/wiki/YAML

        Parameters
        ----------
        as_yaml : :obj:`bool`, optional
            Whether to return the information as a YAML_\-style string.
        indent : :obj:`int`
            The amount of indentation added for each recursive level. Only used if
            `as_yaml` is :obj:`True`.

        Returns
        -------
        :obj:`dict` or :obj:`str`
            The :obj:`~msl.network.network.Network.identity` of the Network
            :class:`~msl.network.manager.Manager`.
        """
        identity = self._send_request_for_manager('identity')
        if not as_yaml:
            return identity
        space = ' ' * indent
        s = ['Manager[{}:{}]'.format(identity["hostname"], identity["port"])]
        for key in sorted(identity):
            if key in ('clients', 'services', 'hostname', 'port'):
                pass
            elif key == 'attributes':
                s.append(space + 'attributes:')
                for item in sorted(identity[key]):
                    s.append(2 * space + '{}: {}'.format(item, identity[key][item]))
            else:
                s.append(space + '{}: {}'.format(key, identity[key]))
        s.append('Clients [{}]:'.format(len(identity["clients"])))
        for address in sorted(identity['clients']):
            s.append(space + '{}[{}]'.format(identity["clients"][address]["name"], address))
            keys = identity['clients'][address]
            for key in sorted(keys):
                if key == 'name':
                    continue
                s.append(2 * space + '{}: {}'.format(key, keys[key]))
        s.append('Services [{}]:'.format(len(identity["services"])))
        for name in sorted(identity['services']):
            s.append(space + '{}[{}]'.format(name, identity["services"][name]["address"]))
            service = identity['services'][name]
            for key in sorted(service):
                if key == 'attributes':
                    s.append(2 * space + 'attributes:')
                    for item in sorted(service[key]):
                        s.append(3 * space + '{}: {}'.format(item, service[key][item]))
                elif key == 'address':
                    continue
                else:
                    s.append(2 * space + '{}: {}'.format(key, service[key]))
        return '\n'.join(s)

    def admin_request(self, attrib, *args, **kwargs):
        """Request something from the Network :class:`~msl.network.manager.Manager`
        as an administrator.

        The user that calls this method must have administrative privileges for that
        Network :class:`~msl.network.manager.Manager`. See also :mod:`msl.network.cli_user`
        for details on how to create a user that is an administrator .

        Parameters
        ----------
        attrib : :obj:`str`
            The attribute of the Network :class:`~msl.network.manager.Manager`. Can contain
            dots ``.`` to access sub-attributes.
        args : :obj:`list`, optional
            The arguments to send to the Network :class:`~msl.network.manager.Manager`.
        kwargs : :obj:`dict`, optional
            The keyword arguments to send to the Network :class:`~msl.network.manager.Manager`.

        Returns
        -------
        The reply from the Network :class:`~msl.network.manager.Manager`.

        Examples
        --------
        ``admin_request('users_table.usernames')``

        ``admin_request('users_table.is_user_registered', 'n.bohr')``

        ``admin_request('connections_table.connections', timestamp1='2017-11-29', timestamp2='2017-11-30')``

        ``admin_request('shutdown_manager')``
        """
        reply = self._send_request_for_manager(attrib, *args, **kwargs)
        if 'result' not in reply:
            # then we need to send an admin username and password
            result = None
            for method in ('username', 'password'):
                uid = self._create_future()
                if method == 'username':
                    self.send_reply(self._transport, self.username(reply['requester']))
                else:
                    self.send_reply(self._transport, self.password(self._username))
                self._wait(uid)
                if method == 'password' and attrib != 'shutdown_manager':
                    result = self._futures[uid].result()['result']
                self._remove_future(uid)
            return result
        return reply['result']

    def connection_made(self, transport):
        """
        .. attention::
           Do not call this method. It is called automatically when the connection
           to the Network :class:`~msl.network.manager.Manager` has been established.
        """
        self._transport = transport
        self._port = int(transport.get_extra_info('sockname')[1])
        self._network_name = '{}[{}]'.format(self.name, self._port)
        if self._debug:
            log.debug(str(self) + ' connection made')

    def data_received(self, reply):
        """
        .. attention::
           Do not call this method. It is called automatically when data is
           received from the Network :class:`~msl.network.manager.Manager`.
        """
        if not self._buffer:
            self._t0 = time.perf_counter()

        # there is a chunk-size limit of 2**14 for each reply
        # keep reading data on the stream until the TERMINATION bytes are received
        self._buffer.extend(reply)
        if not reply.endswith(self.TERMINATION):
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

        data = deserialize(buffer_bytes)
        if data['error']:
            self._latest_error = '\n'.join(['\n'] + data['traceback'] + [data['message']])
            for future in self._futures.values():
                future.cancel()
        elif not self._handshake_finished:
            self.send_reply(self._transport, getattr(self, data['attribute'])(*data['args'], **data['kwargs']))
            self._handshake_finished = data['attribute'] == 'identity'
        elif data['uuid']:
            self._futures[data['uuid']].set_result(data['result'])
        else:
            # performing an admin_request
            assert len(self._futures) == 1, 'uuid not defined and {} futures are available'.format(len(self._futures))
            uid = list(self._futures.keys())[0]
            self._futures[uid].set_result(data)

    def connection_lost(self, exc):
        """
        .. attention::
           Do not call this method. It is called automatically when the connection
           to the Network :class:`~msl.network.manager.Manager` has been closed.
           Call :meth:`disconnect` to close the connection.
        """
        if self._debug:
            log.debug(str(self) + ' connection lost')
        for future in self._futures.values():
            future.cancel()
        self._transport = None
        self._address_manager = None
        self._port = None
        self._loop.stop()
        if exc:
            raise exc

    def spawn(self, name='Client'):
        """Returns a new connection to the Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        name : :obj:`str`, optional
            The name to assign to the new :class:`Client`.

        Returns
        -------
        :class:`Client`:
            A new Client.
        """
        return connect(name=name, host=self._host_manager, port=self._port_manager,
                       timeout=self._timeout, username=self._username, password=self._password,
                       password_manager=self._password_manager, certificate=self._certificate,
                       disable_tls=self._disable_tls, debug=self._debug)

    def raise_latest_error(self):
        """
        Raises the latest error that was received from the Network
        :class:`~msl.network.manager.Manager` as a :exc:`~msl.network.exceptions.MSLNetworkError`
        exception.

        If there is no error then calling this method does nothing.
        """
        if self._latest_error:
            # need to clear the latest error message and all futures in case
            # the Client is connected to the Manager using Python's interactive console
            msg = self._latest_error
            self._latest_error = ''
            self._clear_all_futures()
            raise MSLNetworkError(msg)

    def send_request(self, service, attribute, *args, **kwargs):
        """Send a request to a :class:`~msl.network.service.Service` on the
        Network :class:`~msl.network.manager.Manager`.

        Although a :class:`Client` can call this method directly, in general, it is
        recommended to create a :meth:`link` with a :class:`~msl.network.service.Service`
        and to send requests via the :class:`Link` object. This allows for using the dot
        notation ``.`` for accessing an `attribute` from the :class:`~msl.network.service.Service`
        class.

        Parameters
        ----------
        service : :obj:`str`
            The name of the :class:`~msl.network.service.Service`
        attribute : :obj:`str`
            The name of the property or method of the :class:`~msl.network.service.Service`
            to process the request.
        args : :obj:`list`, optional
            The arguments that the :class:`~msl.network.service.Service` `attribute`
            requires.
        kwargs : :obj:`dict`, optional
            The keyword arguments that the :class:`~msl.network.service.Service`
            `attribute` requires.

        Returns
        -------
        The result from the :class:`~msl.network.service.Service` executing the request, or
        an :class:`asyncio.Future` object if the ``async=True`` keyword argument is specified.

            If sending asynchronous requests then you must call :meth:`send_pending_requests`
            to be able to get the result from each :class:`asyncio.Future`.

        Raises
        ------
        ConnectionError
            If the connection to the Network :class:`~msl.network.manager.Manager`
            has been disconnected.
        ValueError
            If there are asynchronous requests pending and a synchronous request is made.
        :exc:`~msl.network.exceptions.MSLNetworkError`
            If there was an error executing the request.

        Example
        -------
        The following example shows how the :meth:`link` and :meth:`send_request` methods
        can be used to send a request to a :class:`~msl.network.service.Service`

        >>> from msl.network import connect  # doctest: +SKIP

        connect to the Network :class:`~msl.network.manager.Manager` at ``localhost``

        >>> c = connect()  # doctest: +SKIP

        using the :meth:`send_request` method to send requests to the example :ref:`basic-math-service`

        >>> c.send_request('BasicMath', 'add', 2, 3)  # doctest: +SKIP
        5
        >>> c.send_request('BasicMath', 'subtract', 2, 3)  # doctest: +SKIP
        -1

        using the :meth:`link` method to create a link with the :ref:`basic-math-service` and then send requests

        >>> bm = c.link('BasicMath')  # doctest: +SKIP
        >>> bm.add(2, 3)  # doctest: +SKIP
        5
        >>> bm.subtract(2, 3)  # doctest: +SKIP
        -1

        """
        send_asynchronously = kwargs.pop('async', False)
        if not send_asynchronously and self._futures:
            raise ValueError('Asynchronous requests are pending. '
                             'You must call the wait() method to wait for them to '
                             'finish before sending a synchronous request')

        uid = self._create_request(service, attribute, *args, **kwargs)
        if send_asynchronously:
            return self._futures[uid]
        else:
            self.send_data(self._transport, self._requests[uid])
            self._wait(uid)
            result = self._futures[uid].result()
            self._remove_future(uid)
            return result

    def send_pending_requests(self, wait=True):
        """Send all pending requests to the Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        wait : :obj:`bool`, optional
            Whether to wait for all pending requests to finish before returning to
            the calling program. If wait is :obj:`True` then this method will block
            until all requests are done executing. If wait is :obj:`False` then this
            method will return immediately and you must call the :meth:`wait` method
            to ensure that all pending requests have a result.
        """
        for request in self._requests.values():
            if self._debug:
                log.debug('sending request to {}.{}'.format(request["service"], request["attribute"]))
            self.send_data(self._transport, request)
        self._pending_requests_sent = True
        if wait:
            self._wait()

    def start(self, host, port, timeout, username, password, password_manager, certificate, disable_tls, debug):
        """
        .. attention::
            Do not call this method directly. Use :meth:`connect` to connect to
            a Network :class:`~msl.network.manager.Manager`.
        """
        self._host_manager = HOSTNAME if host in localhost_aliases() else host
        self._port_manager = port
        self._disable_tls = bool(disable_tls)
        self._debug = bool(debug)
        self._username = username
        self._password = password
        self._password_manager = password_manager
        self._certificate = certificate
        self._address_manager = '{}:{}'.format(host, port)
        self._timeout = timeout

        context = None
        if not self._disable_tls:
            context = get_ssl_context(host=self._host_manager, port=port, certificate=certificate)
            if not context:
                return
            context.check_hostname = host != HOSTNAME

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(
                self._loop.create_connection(
                    lambda: self,
                    host=self._host_manager,
                    port=port,
                    ssl=context,
                )
            )
        except ssl.SSLError as e:
            e.strerror += '\nTry setting disable_tls=True when connecting to the Manager'
            raise

        async def wait_for_handshake():
            while not self._handshake_finished:
                await asyncio.sleep(0.01)

        try:
            self._loop.run_until_complete(wait_for_handshake())
        except RuntimeError:  # raised if the authentication step failed
            return False

        def run_forever():
            try:
                self._loop.run_forever()
            except KeyboardInterrupt:
                log.debug('CTRL+C keyboard interrupt received')
            finally:
                log.debug('closing the event loop')
                self._loop.close()

        thread = threading.Thread(target=run_forever)
        thread.daemon = True
        thread.start()
        return True

    def wait(self):
        """This method will not return until all pending requests are done executing."""
        if not self._pending_requests_sent:
            self.send_pending_requests(False)
        self._wait()
        self._pending_requests_sent = False

    def _wait(self, uid=None):
        # Do not use asyncio.wait_for and asyncio.wait since they are coroutines.
        # The Client class is considered as a synchronous class by default that
        # has the capability for asynchronous behaviour if the user wants it.
        # Using asyncio.wait_for and asyncio.wait would require the user to use
        # "await" in their code and that is not what is desired.

        def done():
            if uid:
                return self._futures[uid].done()
            else:
                return all(fut.done() for fut in self._futures.values())

        if self._debug:
            log.debug('waiting for futures...')

        t0 = time.perf_counter()
        while not done():
            time.sleep(0.01)
            if self._timeout and time.perf_counter() - t0 > self._timeout:
                err = 'The following requests are still pending: '
                requests = []
                for uid, future in self._futures.items():
                    if not future.done():
                        requests.append('{}.{}'.format(
                            self._requests[uid]["service"], self._requests[uid]["attribute"]
                        ))
                err += ', '.join(requests)
                raise TimeoutError(err)

        if self._debug:
            log.debug('done waiting for futures')

        # check if a future was cancelled
        # this will occur if the Network Manager returned an error
        for future in self._futures.values():
            if future.cancelled():
                self.raise_latest_error()

        if uid is None:
            self._clear_all_futures()

    def _create_future(self):
        uid = str(uuid.uuid4())
        self._futures[uid] = self._loop.create_future()
        if self._debug:
            log.debug('created future[{}]'.format(uid))
        return uid

    def _remove_future(self, uid):
        del self._futures[uid]
        if self._debug:
            log.debug('removed future[{}]; {} pending'.format(uid, len(self._futures)))
        try:
            # In general, we want to delete the request when the future is deleted.
            # However, the admin_request() method does not create a new self._request[uid]
            # when the Manager is requesting the username and password from the Client.
            del self._requests[uid]
        except KeyError:
            pass

    def _clear_all_futures(self):
        self._futures.clear()
        self._requests.clear()
        if self._debug:
            log.debug('removed all futures')

    def _create_request(self, service, attribute, *args, **kwargs):
        if self._transport is None:
            raise ConnectionError(str(self) + ' has been disconnected')
        uid = self._create_future()
        self._requests[uid] = {
            'service': service,
            'attribute': attribute,
            'args': args,
            'kwargs': kwargs,
            'uuid': uid,
            'error': False,
        }
        if self._debug:
            log.debug('created request {}.{} [{} pending]'.format(service, attribute, len(self._requests)))
        return uid

    def _send_request_for_manager(self, attribute, *args, **kwargs):
        # the request is for the Manager to handle, not for a Service
        if self._debug:
            log.debug('sending request to Manager.' + attribute)
        uid = self._create_request('Manager', attribute, *args, **kwargs)
        self.send_data(self._transport, self._requests[uid])
        self._wait(uid)
        if self._futures[uid].cancelled():
            # this section of the code will be reached if the Manager is using the
            # users login credentials for authorization and the Client requested
            # to shutdown the Manager. The connection is lost so
            self._remove_future(uid)
            return {'result': None}
        else:
            result = self._futures[uid].result()
        self._remove_future(uid)
        return result


class Link(object):

    def __init__(self, client, service, identity):
        """A network link between a :class:`Client` and a :class:`~msl.network.service.Service`.

        .. attention::
            Not to be instantiated directly. A :class:`Client` creates a :class:`Link`
            via the :meth:`Client.link` method.
        """
        self._client = client
        self._service_name = service
        self._service_identity = identity
        if client._debug:
            log.debug('linked with {}[{}]'.format(service, identity["address"]))

    @property
    def service_name(self):
        """:obj:`str`: The name of the :class:`~msl.network.service.Service` that this object is linked with."""
        return self._service_name

    @property
    def service_address(self):
        """:obj:`str`: The address of the :class:`~msl.network.service.Service` that this object is linked with."""
        return self._service_identity['address']

    @property
    def service_attributes(self):
        """:obj:`dict`: The attributes of the :class:`~msl.network.service.Service`
        that this object is linked with."""
        return self._service_identity['attributes']

    @property
    def service_language(self):
        """:obj:`str`: The programming language that the :class:`~msl.network.service.Service` is running on."""
        return self._service_identity['language']

    @property
    def service_os(self):
        """:obj:`str`: The operating system that the :class:`~msl.network.service.Service` is running on."""
        return self._service_identity['os']

    def __repr__(self):
        return '<Link with {}[{}] at Manager[{}]>'.format(
            self.service_name, self.service_address, self._client.address_manager)

    def __getattr__(self, item):
        def service_request(*args, **kwargs):
            return self._client.send_request(self._service_name, item, *args, **kwargs)
        return service_request
