"""
Base class for all Clients.
"""
import json
import asyncio
import logging

from .network import Network
from .utils import get_ssl_context

log = logging.getLogger(__name__)


class Client(Network, asyncio.Protocol):

    def __init__(self):
        """Base class for all Clients."""
        self._loop = None
        self._password = None
        self._transport = None
        self._identity = {'type': 'client'}
        self._debug = None
        self._address = None
        self._service = None
        self._attribute = None
        self._handshake_finished = False

    def __getattr__(self, item):
        self._attribute = item
        return self._request

    def __getitem__(self, item):
        self._attribute = item
        return self._request

    def link(self, service):
        # TODO check that the service is available on the Manager
        self._service = service

    def _request(self, **kwargs):
        if self._service is None:
            raise ValueError('The client is not yet linked to a Service')
        return self.send_request(self._transport, service=self._service, attribute=self._attribute, parameters=kwargs)

        # TODO need to figure out how to get the request from data_received...

    def __repr__(self):
        # TODO get the identity from the Manager
        identity = self.send_request(self._transport, service=None, attribute='identity')
        print(identity)

        s = 'Network Manager at {}:{}\n\n'.format(identity['hostname'], identity['port'])
        s += 'Services:\n'
        for name in sorted(identity['services']):
            s += '  {}:\n'.format(name)
            s += '    attributes:\n'
            for attrib in sorted(identity['services']['attributes']):
                s += '      {}: {}\n'.format(attrib, self._services[name]['attributes'][attrib])
        s += '\nClients:\n'
        for c in sorted(identity['clients']):
            s += '  {}\n'.format(c)
        return s

    def __str__(self):
        return '<{} at {:#x} Linked to {}>'.format(self.__class__.__name__, id(self), self._service)

    def password(self, hostname):
        """:obj:`str`: The password required to connect to the Manager at `hostname`."""
        if self._password is None:
            return input(f'Enter the password for {hostname}: ')
        return self._password

    def identity(self):
        """:obj:`dict`: The identity of the :class:`Client`."""
        return self._identity

    def connection_made(self, transport):
        """Automatically called when the connection to the Manager is established."""
        self._transport = transport
        log.info(f'connected to {self._address}')

    def data_received(self, reply):
        data = json.loads(reply)
        if not self._handshake_finished:
            if data['attribute'] == 'password':
                self.send_reply(self._transport, self.password(**data['parameters']))
            elif data['attribute'] == 'identity':
                self.send_reply(self._transport, self.identity())
                self._handshake_finished = True
            else:
                assert False, 'received {} as a handshake attribute'.format(data['attribute'])
        else:
            print(data)

    def connection_lost(self, exc):
        """Automatically called when the Manager closes the connection."""
        log.info(f'disconnected from {self._address}')
        self._loop.stop()
        if exc:
            raise exc

    async def finish_handshake(self):
        while not self._handshake_finished:
            await asyncio.sleep(0.1)

    def start(self, host, port, password, certificate, debug):
        """Start the connection to the Manager.

        Do not call directly. Use :meth:`~msl.network.connection.connect` to
        connect to a network Manager.

        Parameters
        ----------
        host : :obj:`str`
            The hostname of the :class:`Manager` that the :class:`Client`
            should connect to.
        port : :obj:`int`, optional
            The port number of the :class:`Manager` that the :class:`Client`
            should connect to.
        password : :obj:`str`, optional
            The password that is required to connect to the Manager.
            If not specified then you will be asked for the password (only if
            the Manager requires a password to be able to connect to it).
        certificate : :obj:`str`, optional
            The path to the certificate file to use for the TLS connection
            with the Manager.
        debug : :obj:`bool`, optional
            Whether to log debug messages for the :class:`Client`.
        """
        self._debug = debug
        self._password = password
        self._address = f'{host}:{port}'

        context = get_ssl_context(host, port, certificate)
        if not context:
            return

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._loop.run_until_complete(
            self._loop.create_connection(
                lambda: self,
                host=host,
                port=port,
                ssl=context,
            ))

        self._loop.run_until_complete(self.finish_handshake())

        try:
            log.info(f'client running on {self._address}')
            self._loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self._loop.close()
