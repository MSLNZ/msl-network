"""
Use the :func:`connect` function to connect to the Network
:class:`~msl.network.manager.Manager` as a :class:`Client`
"""
import uuid
import asyncio
import getpass
import logging
import platform
import threading
from time import (
    perf_counter,
    sleep,
)

from .network import Network
from .json import deserialize
from .exceptions import MSLNetworkError
from .service import filter_service_start_kwargs
from .utils import (
    localhost_aliases,
    _is_manager_regex,
)
from .constants import (
    PORT,
    HOSTNAME,
    DISCONNECT_REQUEST,
)

log = logging.getLogger(__name__)


def connect(*, name='Client', host='localhost', port=PORT, timeout=10, username=None,
            password=None, password_manager=None, certfile=None, disable_tls=False,
            assert_hostname=True, debug=False):
    """Create a new connection to a Network :class:`~msl.network.manager.Manager`
    as a :class:`Client`.

    .. versionchanged:: 0.4
       Renamed `certificate` to `certfile`.

    Parameters
    ----------
    name : :class:`str`, optional
        A name to assign to the :class:`Client`.
    host : :class:`str`, optional
        The hostname (or IP address) of the Network :class:`~msl.network.manager.Manager`
        that the :class:`~msl.network.client.Client` should connect to.
    port : :class:`int`, optional
        The port number of the Network :class:`~msl.network.manager.Manager`
        that the :class:`~msl.network.client.Client` should connect to.
    timeout : :class:`float`, optional
        The maximum number of seconds to wait to establish the connection to the
        :class:`~msl.network.manager.Manager` before raising a :exc:`TimeoutError`.
    username : :class:`str`, optional
        The username to use to connect to the Network :class:`~msl.network.manager.Manager`.
        You need to specify a username only if the Network :class:`~msl.network.manager.Manager`
        was started with the ``--auth-login`` flag. If a username is required and you have not
        specified it when you called this function then you will be asked for a username.
    password : :class:`str`, optional
        The password that is associated with `username`. If a password is required and you
        have not specified it when you called this function then you will be asked for the password.
    password_manager : :class:`str`, optional
        The password that is associated with the Network :class:`~msl.network.manager.Manager`.
        You need to specify the password only if the Network :class:`~msl.network.manager.Manager`
        was started with the ``--auth-password`` flag. If a password is required and you
        have not specified it when you called this function then you will be asked for the password.
    certfile : :class:`str`, optional
        The path to the certificate file to use for the secure connection
        with the Network :class:`~msl.network.manager.Manager`.
    disable_tls : :class:`bool`, optional
        Whether to connect to the Network :class:`~msl.network.manager.Manager`
        without using the TLS protocol.
    assert_hostname : :class:`bool`, optional
        Whether to force the hostname of the Network :class:`~msl.network.manager.Manager`
        to match the value of `host`.
    debug : :class:`bool`, optional
        Whether to log :py:ref:`DEBUG <levels>` messages for the :class:`Client`.

    Returns
    -------
    :class:`Client`
        A new connection.

    Examples
    --------
    ::

        >>> from msl.network import connect
        >>> cxn = connect()  # doctest: +SKIP
    """
    client = Client(name)
    success = client.start(host, port, timeout, username, password, password_manager,
                           certfile, disable_tls, assert_hostname, debug)
    if not success:
        client.raise_latest_error()
    return client


def filter_client_connect_kwargs(**kwargs):
    """From the specified keyword arguments only return those that are valid for
    :func:`.connect`.

    .. versionadded:: 0.4

    Parameters
    ----------
    kwargs
        Keyword arguments. All keyword arguments that are not part of the method
        signature for :func:`.connect` are silently ignored.

    Returns
    -------
    :class:`dict`
        Valid keyword arguments that can be passed to :func:`.connect`.
    """
    # a Client uses the same keyword arguments (plus an additional `name` kwarg) to
    # connect to a Manager as a Service does, so we can use the same parser function
    kws = filter_service_start_kwargs(**kwargs)
    if 'name' in kwargs:
        kws['name'] = kwargs['name']
    return kws


class Client(Network, asyncio.Protocol):

    def __init__(self, name):
        """Base class for all Clients.

        .. attention::
            Do not instantiate directly. Use :meth:`connect` to connect to
            a Network :class:`~msl.network.manager.Manager`.
        """
        Network.__init__(self)
        asyncio.Protocol.__init__(self)
        self._name = name
        self._port = None
        self._disable_tls = False
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
        self._latest_error = None
        self._buffer = bytearray()
        self._timeout = None
        self._t0 = None  # used for profiling sections of the code
        self._requests = dict()
        self._futures = dict()
        self._pending_requests_sent = False
        self._assert_hostname = True

    @property
    def name(self):
        """:class:`str`: The name of the :class:`Client` on the Network
        :class:`~msl.network.manager.Manager`."""
        return self._name

    @property
    def port(self):
        """:class:`int`: The port number on ``localhost`` that is being used for the
        connection to the Network :class:`~msl.network.manager.Manager`."""
        return self._port

    @property
    def address_manager(self):
        """:class:`str`: The address of the Network :class:`~msl.network.manager.Manager`
        that this :class:`Client` is connected to."""
        return self._address_manager

    def __repr__(self):
        return '<{} manager={} port={}>'.format(self._name, self._address_manager, self._port)

    def password(self, name):
        """
        .. attention::
           Do not call this method. It is called by the Network
           :class:`~msl.network.manager.Manager` when verifying the login credentials.
        """
        # note that a Service has a special check in its password() method so that a password
        # remains secure, however, a Client does not need this security check because a Client
        # cannot send a request to other Clients
        self._connection_successful = True
        if _is_manager_regex.search(name) is not None:
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
        self._connection_successful = True
        if self._username is None:
            self._username = input('Enter the username for ' + name + ' > ')
        return self._username

    def identity(self):
        """:class:`dict`: Returns the :obj:`~msl.network.network.Network.identity` of the :class:`Client`."""
        return self._identity

    def link(self, service, *, timeout=None):
        """Link with a :class:`~msl.network.service.Service` on the Network
        :class:`~msl.network.manager.Manager`.

        .. versionchanged:: 0.3
           Added the `timeout` keyword argument.

        Parameters
        ----------
        service : :class:`str`
            The name of the :class:`~msl.network.service.Service` to link with.
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for the reply from the Network
            :class:`~msl.network.manager.Manager` before raising a :exc:`TimeoutError`.

        Returns
        -------
        :class:`~msl.network.client.Link`
            A :class:`~msl.network.client.Link` with the requested `service`.

        Raises
        ------
        :class:`~msl.network.exceptions.MSLNetworkError`
            If there is no :class:`~msl.network.service.Service` available
            with the name `service`.
        TimeoutError
            If linking with the :class:`~msl.network.service.Service` takes longer
            than `timeout` seconds.
        """
        if self._debug:
            log.debug('preparing to link with {!r}'.format(service))
        identity = self._send_request_for_manager('link', service, timeout=timeout)
        return Link(self, service, identity)

    def disconnect(self):
        """Disconnect from the Network :class:`~msl.network.manager.Manager`."""
        if self._transport is not None:
            uid = self._create_request(self._network_name, DISCONNECT_REQUEST)
            self.send_data(self._transport, self._requests[uid])
            self._wait(uid=uid, timeout=self._timeout)
            self._clear_all_futures()

    def manager(self, *, as_string=False, indent=2, timeout=None):
        """Returns the :obj:`~msl.network.network.Network.identity` of the
        Network :class:`~msl.network.manager.Manager`.

        .. versionchanged:: 0.3
           Added the `timeout` keyword argument.

        .. versionchanged:: 0.4
           Renamed `as_yaml` to `as_string`.

        .. _YAML: https://en.wikipedia.org/wiki/YAML

        Parameters
        ----------
        as_string : :class:`bool`, optional
            Whether to return the information from the Network
            :class:`~msl.network.manager.Manager` as a YAML_\\-style string.
        indent : :class:`int`, optional
            The amount of indentation added for each recursive level. Only used if
            `as_string` is :data:`True`.
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for the reply from the Network
            :class:`~msl.network.manager.Manager` before raising a :exc:`TimeoutError`.

        Returns
        -------
        :class:`dict` or :class:`str`
            The :obj:`~msl.network.network.Network.identity` of the Network
            :class:`~msl.network.manager.Manager`.
        """
        identity = self._send_request_for_manager('identity', timeout=timeout)
        if not as_string:
            return identity
        space = ' ' * indent
        s = ['Manager[{}:{}]'.format(identity['hostname'], identity['port'])]
        for key in sorted(identity):
            if key in ('clients', 'services', 'hostname', 'port'):
                pass
            elif key == 'attributes':
                s.append(space + 'attributes:')
                for item in sorted(identity[key]):
                    s.append(2 * space + '{}{}'.format(item, identity[key][item]))
            else:
                s.append(space + '{}: {}'.format(key, identity[key]))
        s.append('Clients [{}]:'.format(len(identity['clients'])))
        for network_name in sorted(identity['clients']):
            s.append(space + network_name)
            keys = identity['clients'][network_name]
            for key in sorted(keys):
                if key == 'name' or key == 'address':
                    continue
                s.append(2 * space + '{}: {}'.format(key, keys[key]))
        s.append('Services [{}]:'.format(len(identity['services'])))
        for name in sorted(identity['services']):
            s.append(space + '{}[{}]'.format(name, identity['services'][name]['address']))
            service = identity['services'][name]
            for key in sorted(service):
                if key == 'attributes':
                    s.append(2 * space + 'attributes:')
                    for item in sorted(service[key]):
                        signature = service[key][item]
                        if not isinstance(signature, str) or not signature.startswith('('):
                            # then it is a class constant or a property method
                            signature = '() -> {}'.format(signature)
                        s.append(3 * space + '{}{}'.format(item, signature))
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

        .. versionchanged:: 0.3
           Added the `timeout` option as one of the `**kwargs`.

        Parameters
        ----------
        attrib : :class:`str`
            The attribute of the Network :class:`~msl.network.manager.Manager`. Can contain
            dots ``.`` to access sub-attributes.
        *args
            The arguments to send to the Network :class:`~msl.network.manager.Manager`.
        **kwargs
            The keyword arguments to send to the Network :class:`~msl.network.manager.Manager`.
            Also accepts a `timeout` parameter as a :class:`float`.

        Returns
        -------
        The reply from the Network :class:`~msl.network.manager.Manager`.

        Examples
        --------
        ::

            >>> from msl.network import connect  # doctest: +SKIP
            >>> cxn = connect()  # doctest: +SKIP
            >>> unames = cxn.admin_request('users_table.usernames')  # doctest: +SKIP
            >>> is_niels = cxn.admin_request('users_table.is_user_registered', 'n.bohr')  # doctest: +SKIP
            >>> conns = cxn.admin_request('connections_table.connections', timestamp1='2017-11-29', timestamp2='2017-11-30')  # doctest: +SKIP
            >>> cxn.admin_request('shutdown_manager')  # doctest: +SKIP
        """
        # don't pop() the timeout, _send_request_for_manager uses it also
        timeout = kwargs.get('timeout', None)
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
                self._wait(uid=uid, timeout=timeout)
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
            self._t0 = perf_counter()

        # there is a chunk-size limit of 2**14 for each reply
        # keep reading data on the stream until the TERMINATION bytes are received
        self._buffer.extend(reply)
        if not reply.endswith(Network.termination):
            return

        dt = perf_counter() - self._t0
        buffer_bytes = bytes(self._buffer)
        self._buffer.clear()

        if self._debug:
            n = len(buffer_bytes)
            if dt > 0:
                log.debug('{!r} received {} bytes in {:.3g} seconds [{:.3f} MB/s]'.format(
                    self._network_name, n, dt, n*1e-6/dt))
            else:
                log.debug('{!r} received {} bytes in {:.3g} seconds'.format(self._network_name, n, dt))
            if len(buffer_bytes) > self._max_print_size:
                log.debug(buffer_bytes[:self._max_print_size//2] + b' ... ' + buffer_bytes[-self._max_print_size//2:])
            else:
                log.debug(buffer_bytes)

        data = deserialize(buffer_bytes)
        if data['error']:
            self._latest_error = '\n'.join(['\n'] + data['traceback'] + [data['message']])
            for future in self._futures.values():
                future.cancel()
        elif not self._identity_successful:
            self.send_reply(self._transport, getattr(self, data['attribute'])(*data['args'], **data['kwargs']))
            self._identity_successful = data['attribute'] == 'identity'
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
        name : :class:`str`, optional
            The name to assign to the new :class:`Client`.

        Returns
        -------
        :class:`Client`:
            A new Client.
        """
        return connect(name=name, host=self._host_manager, port=self._port_manager,
                       timeout=self._timeout, username=self._username, password=self._password,
                       password_manager=self._password_manager, certfile=self._certificate,
                       disable_tls=self._disable_tls, assert_hostname=self._assert_hostname,
                       debug=self._debug)

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

    def send_pending_requests(self, *, wait=True, timeout=None):
        """Send all pending requests to the Network :class:`~msl.network.manager.Manager`.

        .. versionchanged:: 0.3
           Added the `timeout` keyword argument.

        Parameters
        ----------
        wait : :class:`bool`, optional
            Whether to wait for all pending requests to finish before returning to
            the calling program. If `wait` is :data:`True` then this method will block
            until all requests are done executing. If `wait` is :data:`False` then this
            method will return immediately and you must call the :meth:`wait` method
            to ensure that all pending requests have a result.
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for all pending requests to be
            returned from the Network :class:`~msl.network.manager.Manager` before
            raising a :exc:`TimeoutError`.
        """
        for request in self._requests.values():
            if self._debug:
                log.debug('sending request to {}.{}'.format(request['service'], request['attribute']))
            try:
                self.send_data(self._transport, request)
            except Exception:
                # fixes Issue #5 for asynchronous requests
                self._futures[request['uuid']].cancel()
                self._remove_future(request['uuid'])
                raise
        self._pending_requests_sent = True
        if wait:
            self._wait(timeout=timeout)

    def start(self, host, port, timeout, username, password, password_manager,
              certfile, disable_tls, assert_hostname, debug):
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
        self._certificate = certfile
        self._address_manager = '{}:{}'.format(self._host_manager, port)
        self._timeout = timeout
        self._assert_hostname = bool(assert_hostname)

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        if not self._create_connection(self._host_manager, port, certfile, disable_tls, assert_hostname, timeout):
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

    def wait(self, timeout=None):
        """This method will not return until all pending requests are done executing.

        .. versionchanged:: 0.3
           Added the `timeout` keyword argument.

        Parameters
        ----------
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for the reply from the Network
            :class:`~msl.network.manager.Manager` before raising a :exc:`TimeoutError`.
        """
        if not self._pending_requests_sent:
            self.send_pending_requests(wait=False, timeout=timeout)
        self._wait(timeout=timeout)
        self._pending_requests_sent = False

    def _wait(self, *, uid=None, timeout=None):
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

        t0 = perf_counter()
        while not done():
            sleep(0.01)
            if timeout and perf_counter() - t0 > timeout:
                err = 'The following requests are still pending: '
                requests = []
                for uid, future in self._futures.items():
                    if not future.done():
                        requests.append('{}.{}'.format(
                            self._requests[uid]['service'], self._requests[uid]['attribute']
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
        timeout = kwargs.pop('timeout', None)
        uid = self._create_request('Manager', attribute, *args, **kwargs)
        self.send_data(self._transport, self._requests[uid])
        self._wait(uid=uid, timeout=timeout)
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

    def _send_request(self, service, attribute, *args, **kwargs):
        # Removed as a public API method in v0.4. Linking with a Service is the proper
        # way to send requests to a Service so that the Manager can check if the maximum
        # number of Clients are linked with the Service.
        send_asynchronously = kwargs.pop('asynchronous', False)
        timeout = kwargs.pop('timeout', None)
        if not send_asynchronously and self._futures:
            raise ValueError('Requests are pending. '
                             'You must call the wait() method to wait for them to '
                             'finish before sending another request')

        uid = self._create_request(service, attribute, *args, **kwargs)
        if send_asynchronously:
            return self._futures[uid]
        else:
            try:
                self.send_data(self._transport, self._requests[uid])
            except Exception:
                # fixes Issue #5 for synchronous requests
                self._futures[uid].cancel()
                self._remove_future(uid)
                raise
            else:
                self._wait(uid=uid, timeout=timeout)
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
            log.debug("linked with '{}[{}]'".format(service, identity['address']))

    @property
    def service_name(self):
        """:class:`str`: The name of the :class:`~msl.network.service.Service` that this object is linked with."""
        return self._service_name

    @property
    def service_address(self):
        """:class:`str`: The address of the :class:`~msl.network.service.Service` that this object is linked with."""
        return self._service_identity['address']

    @property
    def service_attributes(self):
        """:class:`dict`: The attributes of the :class:`~msl.network.service.Service`
        that this object is linked with."""
        return self._service_identity['attributes']

    @property
    def service_language(self):
        """:class:`str`: The programming language that the :class:`~msl.network.service.Service` is running on."""
        return self._service_identity['language']

    @property
    def service_os(self):
        """:class:`str`: The operating system that the :class:`~msl.network.service.Service` is running on."""
        return self._service_identity['os']

    def __repr__(self):
        return '<Link with {}[{}] at Manager[{}]>'.format(
            self.service_name, self.service_address, self._client.address_manager)

    def __getattr__(self, item):
        def service_request(*args, **kwargs):
            return self._client._send_request(self._service_name, item, *args, **kwargs)
        return service_request

    def disconnect_service(self, *args, **kwargs):
        """Send a request for the :class:`~msl.network.service.Service` to shut down.

        A :class:`~msl.network.service.Service` must also implement a method called
        ``disconnect_service`` otherwise calling this :meth:`disconnect_service` method
        will raise :class:`~msl.network.exceptions.MSLNetworkError`.

        .. versionadded:: 0.4

        Parameters
        ----------
        args
            The positional arguments that are passed to the ``disconnect_service`` method
            of the :class:`~msl.network.service.Service` that this object is linked with.
        kwargs
            The keyword arguments that are passed to the ``disconnect_service`` method
            of the :class:`~msl.network.service.Service` that this object is linked with.
        """

        # If the request is successful then a ConnectionAbortedError will be raised which
        # is an exception that we expect.
        # However, if a disconnect_service is not available on the Service then we want
        # the AttributeError to be raised
        try:
            self._client._send_request(self._service_name, 'disconnect_service', *args, **kwargs)
        except MSLNetworkError as e:
            traceback = str(e).splitlines()
            if not traceback[-1].startswith('ConnectionAbortedError:'):
                raise


class LinkedClient(object):

    def __init__(self, service_name, **kwargs):
        """Create a new :class:`.Client` that has a :class:`.Link` with the
        specified :class:`~msl.network.service.Service`.

        .. versionadded:: 0.4

        Parameters
        ----------
        service_name : :class:`str`
            The name of the :class:`~msl.network.service.Service` to
            :meth:`~msl.network.client.Client.link` with.
        kwargs
            Keyword arguments that are passed to :func:`.connect`.
        """
        super(LinkedClient, self).__init__()
        if 'name' not in kwargs:
            kwargs['name'] = 'LinkedClient'
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 10
        self._kwargs = filter_client_connect_kwargs(**kwargs)

        # When starting a Manager and a Service on a remote computer there can
        # be a race condition for the Manager to start, the Service to start and
        # for the Client to link with the Service. We consider the `timeout` kwarg
        # to be the total time to connect to the Manager and link with the Service.
        t0 = perf_counter()
        self._cxn = connect(**self._kwargs)

        while True:
            if service_name in self._cxn.manager()['services']:
                break
            if perf_counter() - t0 > self._kwargs['timeout']:
                raise TimeoutError('The {!r} service is not available'.format(service_name))
            sleep(0.5)

        self._link = self._cxn.link(service_name)

    @property
    def address_manager(self):
        """See :obj:`.Client.address_manager` for more details."""
        return self._cxn.address_manager

    @property
    def name(self):
        """See :obj:`.Client.name` for more details."""
        return self._cxn.name

    @property
    def port(self):
        """See :obj:`.Client.port` for more details."""
        return self._cxn.port

    @property
    def service_address(self):
        """See :obj:`.Link.service_address` for more details."""
        return self._link.service_address

    @property
    def service_attributes(self):
        """See :obj:`.Link.service_attributes` for more details."""
        return self._link.service_attributes

    @property
    def service_language(self):
        """See :obj:`.Link.service_language` for more details."""
        return self._link.service_language

    @property
    def service_name(self):
        """See :obj:`.Link.service_name` for more details."""
        return self._link.service_name

    @property
    def service_os(self):
        """See :obj:`.Link.service_os` for more details."""
        return self._link.service_os

    @property
    def link(self):
        """:class:`.Link`: The :class:`.Link` with the :class:`~msl.network.service.Service`."""
        return self._link

    def admin_request(self, attrib, *args, **kwargs):
        """See :meth:`.Client.admin_request` for more details."""
        return self._cxn.admin_request(attrib, *args, **kwargs)

    def disconnect(self):
        """See :meth:`.Client.disconnect` for more details."""
        self._cxn.disconnect()

    def identity(self):
        """See :meth:`.Client.identity` for more details."""
        return self._cxn.identity()

    def manager(self, *, as_string=False, indent=4, timeout=None):
        """See :meth:`.Client.manager` for more details."""
        return self._cxn.manager(as_string=as_string, indent=indent, timeout=timeout)

    def send_pending_requests(self, *, wait=True, timeout=None):
        """See :meth:`.Client.send_pending_requests` for more details."""
        self._cxn.send_pending_requests(wait=wait, timeout=timeout)

    def service_error_handler(self):
        """This method is called immediately before an exception is raised if there
        was an error processing a request on the :class:`~msl.network.service.Service`
        that this object is linked with.

        You can override this method to perform any necessary cleanup (e.g., closing
        file handles, shutting down threads, disconnecting from devices, ...) before
        :class:`~msl.network.exceptions.MSLNetworkError` is raised.
        """
        pass

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

    def wait(self, timeout=None):
        """See :meth:`.Client.wait` for more details."""
        self._cxn.wait(timeout=timeout)

    def __repr__(self):
        return '<Link[name={}] with {}[{}] at Manager[{}]>'.format(
            self.name, self.service_name, self.service_address, self.address_manager
        )

    def __getattr__(self, item):
        # all other methods that are called get sent to the Link object
        def service_request(*args, **kwargs):
            try:
                return getattr(self._link, item)(*args, **kwargs)
            except MSLNetworkError:
                self.service_error_handler()
                raise
        return service_request

    def __del__(self):
        try:
            self.disconnect()
        except:
            pass
