"""
Connect to a Network :class:`~msl.network.manager.Manager`.
"""
import json
import time
import asyncio
import logging
import threading

from collections import deque

from .constants import PORT
from .network import Network
from .utils import get_ssl_context

log = logging.getLogger(__name__)


def connect(name='Client', host='localhost', port=PORT, password=None, certificate=None, debug=False):
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
    password : :obj:`str`, optional
        The password that is required to connect to the Network
        :class:`~msl.network.manager.Manager`. If not specified then you
        will be asked for the password (only if the Network
        :class:`~msl.network.manager.Manager` requires a password to
        be able to connect to it).
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
    success = client.start(host, port, password, certificate, debug)
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
        self._network_id = name
        self._host = None
        self._port = None
        self._loop = None
        self._debug = None
        self._password = None
        self._transport = None
        self._certificate = None
        self._identity = {'type': 'client', 'name': name}
        self._address = None
        self._address_manager = None
        self._network_id = None
        self._service = None
        self._attribute = None
        self._handshake_finished = False
        self._traceback = []
        self._waiter = None
        self._queue = deque()  # TODO implement queue

    @property
    def name(self):
        """:obj:`str`: The name of this connection on the Network :class:`~msl.network.manager.Manager`."""
        return self._name

    @property
    def address(self):
        """:obj:`str`: The address of this connection to the Network :class:`~msl.network.manager.Manager`."""
        return self._address

    @property
    def address_manager(self):
        """:obj:`str`: The address of the Network :class:`~msl.network.manager.Manager`."""
        return self._address_manager

    def __repr__(self):
        return '<{} at {:#x} manager={} address={} service={}>'.format(
            self._name, id(self), self._address_manager, self._address, self._service)

    def __getattr__(self, item):
        self._attribute = item
        return self._request

    def __getitem__(self, item):
        self._attribute = item
        return self._request

    def password(self, hostname):
        """:obj:`str`: The password required to connect to the Network
        :class:`~msl.network.manager.Manager` at `hostname`."""
        if self._password is None:
            self._password = input(f'Enter the password for {hostname}: ')
        return self._password

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
        self._waiter = self._loop.create_future()
        self.send_request(self._transport, service=None, attribute='link', parameters={'service_name': service})
        result = self._wait()
        if result['error']:
            self.raise_latest_error()
        self._service = service

    def disconnect(self):
        """Disconnect from the Network :class:`~msl.network.manager.Manager`."""
        self.send_request(self._transport, service='self', attribute='__disconnect__')

    def manager_identity(self):
        """:obj:`dict`: The :obj:`~msl.network.network.Network.identity` of
        the Network :class:`~msl.network.manager.Manager`."""
        if not self._handshake_finished:
            return None
        self._waiter = self._loop.create_future()
        self.send_request(self._transport, service=None, attribute='identity')
        return self._wait()['return']

    def manager_summary(self):
        """
        :obj:`str`: Returns :meth:`.manager_identity`, but as a YAML_\-style string.

        .. _YAML: https://en.wikipedia.org/wiki/YAML
        """
        identity = self.manager_identity()
        s = f'*** Summary for the Network Manager at {identity["hostname"]}:{identity["port"]} ***\n'
        s += f'{self._name} is currently linked with {self._service}\n'
        for i, val in enumerate(['manager', 'services']):
            if i == 0:
                s += 'Manager:\n'
            else:
                s += f'Services [{len(identity[val])}]:\n'
            for name in sorted(identity[val]):
                item = identity[val][name]
                s += f'  {name}:\n'
                for key in sorted(item):
                    if key == 'attributes':
                        s += f'    {key}:\n'
                        for attrib in item[key]:
                            s += f'      {attrib}: {item[key][attrib]}\n'
                    else:
                        s += f'    {key}: {item[key]}\n'
        s += f'Clients [{len(identity["clients"])}]:\n'
        for address in sorted(identity['clients']):
            s += f'  {address}\n'
        return s

    def connection_made(self, transport):
        """Automatically called when the connection to the Network
        :class:`~msl.network.manager.Manager` has been established."""
        self._address = '{}:{}'.format(*transport.get_extra_info('sockname'))
        self._network_id = '{}[{}]'.format(self._name, self._address)
        self._transport = transport
        log.debug(f'{self} connection made')

    def data_received(self, reply):
        """New data is received for the :class:`Client`.

        .. _JSON: http://www.json.org/

        Parameters
        ----------
        reply : :obj:`bytes`
            The response from the :class:`~msl.network.service.Service` that the
            :class:`Client` is linked with.

            A :class:`~msl.network.service.Service` will reply with a JSON_ object in
            one of the following formats.

            If the output data represents an error then the JSON_ object will be::

                {
                  'error' : bool (True)
                  'return': null
                  'message': string (a short description of the error)
                  'traceback': list of strings (a detailed stack trace of the error)
                }

            If the output data DOES NOT represent an error then the JSON_ object will be::

                {
                  'error' : bool (False)
                  'return': object (whatever the response is from the Service)
                }

        """
        if self._debug:
            log.debug(f'{self._network_id} received {reply}')

        data = json.loads(reply)
        if data['error']:
            log.error(data['message'])
            self._traceback = data['traceback']
        elif not self._handshake_finished:
            self.send_reply(self._transport, getattr(self, data['attribute'])(**data['parameters']))
            self._handshake_finished = data['attribute'] == 'identity'

        if self._waiter is not None:
            self._waiter.set_result(data)

    def connection_lost(self, exc):
        """Automatically called when the connection to the Network
        :class:`~msl.network.manager.Manager` has been closed."""
        log.debug(f'{self} connection lost')
        self._transport = None
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
        return connect(name, self._host, self._port, self._password, self._certificate, self._debug)

    def raise_latest_error(self):
        """Raises the latest exception that was received from the Network
        :class:`~msl.network.manager.Manager`."""
        if self._handshake_finished:
            self.disconnect()
        raise Exception('\n'.join(self._traceback))

    def start(self, host, port, password, certificate, debug):
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
        password : :obj:`str`, optional
            The password that is required to connect to the Network
            :class:`~msl.network.manager.Manager`. If not specified then you will
            be asked for the password (only if the Network :class:`~msl.network.manager.Manager`
            requires a password to be able to connect to it).
        certificate : :obj:`str`, optional
            The path to the certificate file to use for the TLS connection
            with the Network :class:`~msl.network.manager.Manager`.
        debug : :obj:`bool`, optional
            Whether to log debug messages for the :class:`Client`.
        """
        self._host = host
        self._port = port
        self._debug = debug
        self._password = password
        self._certificate = certificate
        self._address_manager = f'{host}:{port}'

        context = get_ssl_context(host, port, certificate)
        if not context:
            return

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # self._loop.set_debug(debug)

        self._loop.run_until_complete(
            self._loop.create_connection(
                lambda: self,
                host=host,
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
                log.debug(f'{self} connection accepted')
                self._loop.run_forever()
            except KeyboardInterrupt:
                log.debug('CTRL+C keyboard interrupt received')
            finally:
                log.debug(f'{self} disconnected')
                self._loop.close()

        thread = threading.Thread(target=run_forever)
        thread.daemon = True
        thread.start()
        return True

    def _request(self, **kwargs):
        """Send __getattr__ and  __getitem__ requests to the Manager."""
        if self._service is None:
            self.disconnect()
            raise ValueError(f'{self._network_id} has not been linked to a Service yet')
        self._waiter = self._loop.create_future()
        self.send_request(self._transport, service=self._service, attribute=self._attribute, parameters=kwargs)
        result = self._wait()
        if result['error']:
            self.raise_latest_error()
        return result['return']

    def _wait(self):
        """A blocking method. Returns what the waiter is waiting for."""
        while not self._waiter.done():
            log.debug('waiting...')
            time.sleep(0.01)
        log.debug('done waiting')
        return self._waiter.result()
