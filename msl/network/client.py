"""
Connect to a Network :class:`~msl.network.manager.Manager`.
"""
import time
import uuid
import asyncio
import getpass
import logging
import threading

from .network import Network
from .json import deserialize
from .utils import localhost_aliases
from .constants import PORT, HOSTNAME
from .cryptography import get_ssl_context
from .exceptions import NetworkManagerError

log = logging.getLogger(__name__)


def connect(*, name='Client', host='localhost', port=PORT, timeout=None, username=None,
            password=None, password_manager=None, certificate=None, debug=False):
    """Create a new connection to a Network :class:`~msl.network.manager.Manager`.

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
        If not specified then you will be asked for the username (only if the Network
        :class:`~msl.network.manager.Manager` requires login credentials to be able
        to connect to it).
    password : :obj:`str`, optional
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
        Whether to log debug messages for the :class:`Client`.

    Returns
    -------
    :class:`Client`
        A new connection.
    """
    client = Client(name)
    success = client.start(host, port, timeout, username, password, password_manager, certificate, debug)
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
        self._debug = False
        self._username = None
        self._password = None
        self._host_manager = None
        self._port_manager = None
        self._address_manager = None
        self._password_manager = None
        self._transport = None
        self._certificate = None
        self._identity = {'type': 'client', 'name': name}
        self._service = None
        self._attribute = None
        self._handshake_finished = False
        self._latest_error = None
        self._buffer = bytearray()
        self._timeout = None
        self._t0 = None  # used for profiling sections of the code
        self._requests = dict()
        self._futures = dict()

    @property
    def name(self):
        """:obj:`str`: The name of this connection on the Network :class:`~msl.network.manager.Manager`."""
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
        return '<{} object at {:#x} manager={} port={} service={}>'.format(
            self._name, id(self), self._address_manager, self._port, self._service)

    def __getattr__(self, item):
        self._attribute = item
        return self._send_request_for_service

    def __getitem__(self, item):
        self._attribute = item
        return self._send_request_for_service

    def password(self, name):
        """:obj:`str`: The password required to connect to the Network
        :class:`~msl.network.manager.Manager` at `name`."""
        # note that a Service has a special check in its password() method, however,
        # a Client does not need this check because Clients cannot send requests to
        # other Clients and a Manager will not re-ask for the password
        if name == self._address_manager:
            if self._password_manager is None:
                self._password_manager = getpass.getpass(f'Enter the password for {name} > ')
            return self._password_manager
        if self._password is None:
            self._password = getpass.getpass(f'Enter the password for {name} > ')
        return self._password

    def username(self, name):
        """:obj:`str`: The username to use to connect to the Network
        :class:`~msl.network.manager.Manager` at `name`."""
        # see the comment in the Client.password() method and in the Service.username() method
        if self._username is None:
            self._username = input(f'Enter the username for {name} > ')
        return self._username

    def identity(self):
        """:obj:`dict`: The :obj:`~msl.network.network.Network.identity` of the :class:`Client`."""
        return self._identity

    def link(self, service):
        """Link with a :class:`~msl.network.service.Service`.

        Parameters
        ----------
        service : :obj:`str`
            The name of the :class:`~msl.network.service.Service` to link with.

        Raises
        ------
        :class:`Exception`
            If there is no :class:`~msl.network.service.Service` available
            with the name `service`.
        """
        if self._debug:
            log.debug(f'preparing to link with the {service} Service')
        success = self._send_request_for_manager('link', service)
        if success:
            self._service = service
        else:
            self.raise_latest_error()

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
        if self._service:
            service_address = identity["services"][self._service]["address"]
            s = [f'{self._name}[{self._port}] is currently linked with {self._service}[{service_address}]\n']
        else:
            s = [f'{self._name}[{self._port}] is not currently linked with a Service\n']
        s.append(f'Summary for the Network Manager at {self._address_manager}\n')
        s.append('Manager:\n')
        for key in sorted(identity):
            if key == 'clients' or key == 'services':
                pass
            elif key == 'attributes':
                s.append(space + 'attributes:\n')
                for item in sorted(identity[key]):
                    s.append(2 * space + f'{item}: {identity[key][item]}\n')
            else:
                s.append(space + f'{key}: {identity[key]}\n')
        s.append(f'Clients [{len(identity["clients"])}]:\n')
        for client in sorted(identity['clients']):
            s.append(space + f'{identity["clients"][client]}: {client}\n')
        s.append(f'Services [{len(identity["services"])}]:\n')
        for name in sorted(identity['services']):
            s.append(space + f'{name}:\n')
            service = identity['services'][name]
            for key in sorted(service):
                if key == 'attributes':
                    s.append(2 * space + 'attributes:\n')
                    for item in sorted(service[key]):
                        s.append(3 * space + f'{item}: {service[key][item]}\n')
                else:
                    s.append(2 * space + f'{key}: {service[key]}\n')
        return ''.join(s)

    def admin_request(self, attrib, *args, **kwargs):
        """Request something from the Network :class:`~msl.network.manager.Manager`
        as an administrator.

        The person that calls this method must have administrative privileges for that
        Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        attrib : :obj:`str`
            The attribute on the Network :class:`~msl.network.manager.Manager`. Can contain
            dots ``.`` to access sub-attributes.
        args : :obj:`list`
            The arguments to send to the Network :class:`~msl.network.manager.Manager`.
        kwargs : :obj:`dict`
            The keyword arguments to send to the Network :class:`~msl.network.manager.Manager`.

        Returns
        -------
        The reply from the Network :class:`~msl.network.manager.Manager`.
        """
        reply = self._send_request_for_manager(attrib, *args, **kwargs)
        if 'result' not in reply:
            # then we need to send an admin username and password
            for method in ('username', 'password'):
                uid = self._create_future()
                if method == 'username':
                    self.send_reply(self._transport, self.username(reply['requester']))
                else:
                    self.send_reply(self._transport, self.password(self._username))
                self._wait(uid)
                if method == 'password':
                    result = self._futures[uid].result()['result']
                self._remove_future(uid)
            return result
        return reply['result']

    def connection_made(self, transport):
        """Automatically called when the connection to the Network
        :class:`~msl.network.manager.Manager` has been established."""
        self._transport = transport
        self._port = int(transport.get_extra_info('sockname')[1])
        self._network_name = '{}[{}]'.format(self.name, self._port)
        log.debug(f'{self} connection made')

    def data_received(self, reply):
        """New data is received for the :class:`Client`.

        .. _JSON: http://www.json.org/

        Parameters
        ----------
        reply : :obj:`bytes`
            The reply from the :class:`~msl.network.service.Service` or the
            Network :class:`~msl.network.manager.Manager`.

            A :class:`Client` receives data that will be converted into a JSON_ object.
            The input data **MUST** have one of the following formats.

            If the input data represents an error then the JSON_ object will be::

                {
                    'error' : boolean (True)
                    'message': string (a short description of the error)
                    'traceback': list of strings (a detailed stack trace of the error)
                    'result': null
                    'requester': string (the address of the device that made the request)
                }

            If the output data **does not** represent an error then the JSON_ object
            will be::

                {
                    'result': object (whatever the reply is from the Service)
                    'requester': string (the address of the device that made the request)
                    'uuid' string (the universally unique identifier of the request)
                    'error' : boolean (False)
                }

        """
        if not self._buffer:
            self._t0 = time.perf_counter()

        # there is a chunk-size limit of 2**14 for each reply
        # keep reading the data on the stream until the \n character is received
        self._buffer.extend(reply)
        if not reply.endswith(b'\n'):
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
            assert len(self._futures) == 1, f'uuid not defined and {len(self._futures)} futures are available'
            uid = list(self._futures.keys())[0]
            self._futures[uid].set_result(data)

    def connection_lost(self, exc):
        """Automatically called when the connection to the Network
        :class:`~msl.network.manager.Manager` has been closed."""
        log.debug(f'{self} connection lost')
        for future in self._futures.values():
            future.cancel()
        self._transport = None
        self._address_manager = None
        self._port = None
        self._service = None
        self._attribute = None
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
        return connect(name=name, host=self._host_manager, port=self._port_manager, timeout=self._timeout,
                       username=self._username, password=self._password, password_manager=self._password_manager,
                       certificate=self._certificate, debug=self._debug)

    def raise_latest_error(self):
        """Raises the latest exception that was received from the Network
        :class:`~msl.network.manager.Manager`. If there is no error then
        calling this method does nothing."""
        if self._latest_error:
            raise NetworkManagerError(self._latest_error)

    def start(self, host, port, timeout, username, password, password_manager, certificate, debug):
        """Start the connection to a Network :class:`~msl.network.manager.Manager`.

        .. attention::
            Do not call this method directly. Use :meth:`connect` to connect to
            a Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        host : :obj:`str`, optional
            The hostname of the Network :class:`~msl.network.manager.Manager` that the
            :class:`Client` should connect to.
        port : :obj:`int`, optional
            The port number of the Network :class:`~msl.network.manager.Manager` that
            the :class:`Client` should connect to.
        timeout : :obj:`float`
            The maximum number of seconds to wait for a reply from the Network
            :class:`~msl.network.manager.Manager` before raising a :exc:`TimeoutError`.
        username : :obj:`str`, optional
            The username to use to connect to Network :class:`~msl.network.manager.Manager`.
            If not specified then you will be asked for the username (only if the Network
            :class:`~msl.network.manager.Manager` requires login credentials to be able
            to connect to it).
        password : :obj:`str`, optional
            The password that is associated with `username`. Can be specified if the Network
            :class:`~msl.network.manager.Manager` requires a login to connect to it. If the
            `password` is not specified then you will be asked for the password if needed.
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
            Whether to log debug messages for the :class:`Client`.
        """
        self._host_manager = HOSTNAME if host in localhost_aliases() else host
        self._port_manager = port
        self._debug = bool(debug)
        self._username = username
        self._password = password
        self._password_manager = password_manager
        self._certificate = certificate
        self._address_manager = f'{host}:{port}'
        self._timeout = timeout

        context = get_ssl_context(host=self._host_manager, port=port, certificate=certificate)
        if not context:
            return
        context.check_hostname = host != HOSTNAME

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # self._loop.set_debug(debug)

        self._loop.run_until_complete(
            self._loop.create_connection(
                lambda: self,
                host=self._host_manager,
                port=port,
                ssl=context,
            )
        )

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
        for data in self._requests.values():
            if self._debug:
                log.debug(f'sending request to {data["service"]}.{data["attribute"]}')
            self.send_data(self._transport, data)
        self._wait()
        self._clear_all_futures()

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
                        requests.append(f'{self._requests[uid]["service"]}.{self._requests[uid]["attribute"]}')
                err += ', '.join(requests)
                raise TimeoutError(err)

        if self._debug:
            log.debug('done waiting for futures')

        # check if a future was cancelled
        # this will occur if the Network Manager returned an error
        for future in self._futures.values():
            if future.cancelled():
                self.raise_latest_error()

    def _create_future(self):
        uid = str(uuid.uuid4())
        self._futures[uid] = self._loop.create_future()
        return uid

    def _remove_future(self, uid):
        if self._debug:
            log.debug(f'removing future for {self._requests[uid]["service"]}.{self._requests[uid]["attribute"]} '
                      f'[{len(self._requests)-1} pending]')
        del self._futures[uid]
        del self._requests[uid]

    def _clear_all_futures(self):
        self._futures.clear()
        self._requests.clear()

    def _create_request(self, service, attribute, *args, **kwargs):
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
            log.debug(f'created request {service}.{attribute} [{len(self._requests)} pending]')
        return uid

    def _send_request_for_service(self, *args, **kwargs):
        # Send __getattr__ and  __getitem__ requests to the Manager
        if self._service is None:
            raise ValueError(f'{self._network_name} has not been linked to a Service yet')

        send_asynchronously = kwargs.pop('async', False)
        if not send_asynchronously and self._futures:
            raise ValueError('Asynchronous requests are pending. '
                             'You must call the wait() method to wait for them to '
                             'finish before sending a synchronous request')

        uid = self._create_request(self._service, self._attribute, *args, **kwargs)
        if send_asynchronously:
            return self._futures[uid]
        else:
            self.send_data(self._transport, self._requests[uid])
            self._wait(uid)
            result = self._futures[uid].result()
            self._remove_future(uid)
            return result

    def _send_request_for_manager(self, attribute, *args, **kwargs):
        # the request is for the Manager to handle, not for a Service
        if self._debug:
            log.debug(f'sending request to Manager.{attribute}')
        uid = self._create_request('Manager', attribute, *args, **kwargs)
        self.send_data(self._transport, self._requests[uid])
        self._wait(uid)
        result = self._futures[uid].result()
        self._remove_future(uid)
        return result
