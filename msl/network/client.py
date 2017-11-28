"""
Connect to a Network :class:`~msl.network.manager.Manager`.
"""
import sys
import json
import time
import asyncio
import getpass
import logging
import threading

from collections import deque

from .network import Network
from .utils import localhost_aliases
from .constants import PORT, HOSTNAME
from .cryptography import get_ssl_context

log = logging.getLogger(__name__)


def connect(*, name='Client', host='localhost', port=PORT, username=None, password=None,
            password_manager=None, certificate=None, debug=False):
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
    success = client.start(host, port, username, password, password_manager, certificate, debug)
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
        self._debug = None
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
        self._traceback = []
        self._error_message = ''
        self._waiter = None
        self._queue = deque()  # TODO implement queue

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

    def __repr__(self):
        return '<{} object at {:#x} manager={} port={} service={}>'.format(
            self._name, id(self), self._address_manager, self._port, self._service)

    def __getattr__(self, item):
        self._attribute = item
        return self._request

    def __getitem__(self, item):
        self._attribute = item
        return self._request

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
        result = self._send_request_blocking(None, 'link', service)
        if result['error']:
            self.raise_latest_error()
        else:
            self._service = service

    def disconnect(self):
        """Disconnect from the Network :class:`~msl.network.manager.Manager`."""
        self._send_request('self', '__disconnect__', {})

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
        identity = self._send_request_blocking(None, 'identity')['return']
        if not as_yaml:
            return identity
        space = ' ' * indent
        if self._service:
            service_address = identity["services"][self._service]["address"]
            s = f'{self._name}[{self._port}] is currently linked with {self._service}[{service_address}]\n'
        else:
            s = f'{self._name}[{self._port}] is not currently linked with a Service\n'
        s += f'Summary for the Network Manager at {self._address_manager}\n'
        s += 'Manager:\n'
        for key in sorted(identity):
            if key == 'clients' or key == 'services':
                pass
            elif key == 'attributes':
                s += space + 'attributes:\n'
                for item in sorted(identity[key]):
                    s += 2 * space + f'{item}: {identity[key][item]}\n'
            else:
                s += space + f'{key}: {identity[key]}\n'
        s += f'Clients [{len(identity["clients"])}]:\n'
        for client in sorted(identity['clients']):
            s += space + f'{identity["clients"][client]}: {client}\n'
        s += f'Services [{len(identity["services"])}]:\n'
        for name in sorted(identity['services']):
            s += space + f'{name}:\n'
            service = identity['services'][name]
            for key in sorted(service):
                if key == 'attributes':
                    s += 2 * space + 'attributes:\n'
                    for item in sorted(service[key]):
                        s += 3 * space + f'{item}: {service[key][item]}\n'
                else:
                    s += 2 * space + f'{key}: {service[key]}\n'
        return s

    def admin_request(self, attrib, *args, **kwargs):
        """Request something from the Network :class:`~msl.network.manager.Manager`
        as an administrator.

        The person that call this method must have administrative privileges for the
        Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        attrib : :obj:`str`
            The attribute on the Network :class:`~msl.network.manager.Manager`. Can contain
            dots ``.`` to access sub-attributes.
        args : :obj:`list`
            The arguments.
        kwargs : :obj:`dict`
            The keyword arguments.

        Returns
        -------
        The reply from the Network :class:`~msl.network.manager.Manager`.
        """
        result = self._send_request_blocking(None, attrib, *args, **kwargs)

        if result['error']:
            self.raise_latest_error()

        if 'return' not in result:
            # then we need to send the admin's username and password
            self._waiter = self._loop.create_future()
            self.send_reply(self._transport, self.username(self._address_manager))
            result = self._wait()
            if result['error']:  # invalid username
                self.raise_latest_error()
            self._waiter = self._loop.create_future()
            self.send_reply(self._transport, self.password(self._username))
            result = self._wait()
            if result['error']:  # invalid password
                self.raise_latest_error()
            return result['return']

        return result['return']

    def connection_made(self, transport):
        """Automatically called when the connection to the Network
        :class:`~msl.network.manager.Manager` has been established."""
        self._transport = transport
        self._port = int(transport.get_extra_info('sockname')[1])
        self._network_name = '{}[{}]'.format(self.name, self._port)
        log.info(f'{self} connection made')

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

            If the input data represents an error then the JSON_ object must contain::

                {
                    'error' : bool (True)
                    'message': string (a short description of the error)
                    'traceback': list of strings (a detailed stack trace of the error)
                    'return': null
                }

            If the output data DOES NOT represent an error then the JSON_ object must
            contain::

                {
                    'return': object (whatever the reply is from a Service/Manager)
                    'error' : bool (False)
                }

        """
        if self._debug:
            log.debug(f'{self._network_name} received {reply}')

        data = json.loads(reply)
        if data['error']:
            self._error_message = data['message']
            self._traceback = data['traceback']
            log.error(self._error_message)
            if self._error_message.startswith('ConnectionAbortedError:'):
                self.raise_latest_error()
        elif not self._handshake_finished:
            self.send_reply(self._transport, getattr(self, data['attribute'])(*data['args'], **data['kwargs']))
            self._handshake_finished = data['attribute'] == 'identity'

        if self._waiter is not None:
            self._waiter.set_result(data)

    def connection_lost(self, exc):
        """Automatically called when the connection to the Network
        :class:`~msl.network.manager.Manager` has been closed."""
        log.info(f'{self} connection lost')
        self._transport = None
        self._address_manager = None
        self._port = None
        self._service = None
        self._attribute = None
        self._loop.stop()
        if exc:
            log.error(str(exc))
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
        return connect(name=name, host=self._host_manager, port=self._port_manager, username=self._username,
                       password=self._password, password_manager=self._password_manager,
                       certificate=self._certificate, debug=self._debug)

    def raise_latest_error(self):
        """Raises the latest exception that was received from the Network
        :class:`~msl.network.manager.Manager`."""
        if self._handshake_finished:
            self.disconnect()
        raise Exception('\n'.join(self._traceback))

    def print_latest_error(self):
        """Prints the latest exception that was received from the Network
        :class:`~msl.network.manager.Manager` to :obj:`sys.stderr`."""
        print('\n'.join(self._traceback), file=sys.stderr)
        print(self._error_message, file=sys.stderr)

    def start(self, host, port, username, password, password_manager, certificate, debug):
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
        """
        self._host_manager = HOSTNAME if host in localhost_aliases() else host
        self._port_manager = port
        self._debug = debug
        self._username = username
        self._password = password
        self._password_manager = password_manager
        self._certificate = certificate
        self._address_manager = f'{host}:{port}'

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
                self._loop.close()

        thread = threading.Thread(target=run_forever)
        thread.daemon = True
        thread.start()
        return True

    def _request(self, *args, **kwargs):
        """Send __getattr__ and  __getitem__ requests to the Manager."""
        if self._service is None:
            self.disconnect()
            raise ValueError(f'{self._network_name} has not been linked to a Service yet')
        result = self._send_request_blocking(self._service, self._attribute, *args, *kwargs)
        if result['error']:
            # self.raise_latest_error()
            self.print_latest_error()
            return None
        return result['return']

    def _wait(self):
        """A blocking method. Returns what the waiter is waiting for."""
        while not self._waiter.done():
            log.debug('waiting...')
            time.sleep(0.01)
        log.debug('done waiting')
        result = self._waiter.result()
        self._waiter = None
        return result

    def _send_request(self, service, attribute, *args, **kwargs):
        self.send_data(self._transport, {
            'service': service,
            'attribute': attribute,
            'args': args,
            'kwargs': kwargs,
            'error': False,
        })

    def _send_request_blocking(self, service, attribute, *args, **kwargs):
        self._waiter = self._loop.create_future()
        self._send_request(service, attribute, *args, *kwargs)
        return self._wait()
