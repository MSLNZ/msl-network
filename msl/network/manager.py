"""
An asynchronous network manager.
"""
import os
import ssl
import json
import asyncio
import logging
import platform

from .network import Network
from .constants import HOSTNAME
from .database import ConnectionsDatabase

log = logging.getLogger(__name__)


class Manager(Network):

    def __init__(self, port, authentication, database, debug):
        """An asynchronous network manager.

        Not to be instantiated directly. To be called from the command line.
        """
        self.debug = debug
        self.database = database
        self.authentication = authentication
        self.clients = []
        self.services = {}
        self.service_writers = {}
        self.client_writers = {}
        self.client_service_link = {}

        self._identity = {
            'hostname': HOSTNAME,
            'port': port,
            'language': 'Python ' + platform.python_version(),
            'os': '{} {} {}'.format(platform.system(), platform.release(), platform.machine()),
            'clients': self.clients,
            'services': self.services,
            'manager': {
                'identity': '() -> dict',
                'link': '(client_address:str, service_name:str) -> bool',
            }
        }

    async def new_connection(self, reader, writer):
        """Receive a new connection request.

        To accept the new connection request, the following checks must be successful:

        1. The correct authentication reply is received.
        2. A correct :obj:`~msl.network.network.Network.identity` is received,
           i.e., is the connection from a client or service?

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.
        """
        peer = writer.get_extra_info('peername')
        address = '{}:{}'.format(peer[0], peer[1])
        log.info(address + ' new connection')

        # check the authentication (either a list of trusted hostname's or a password)
        if self.authentication is not None:
            log.info(address + ' checking authentication')
            if isinstance(self.authentication, list):
                if peer[0] not in self.authentication:
                    self.database.insert(peer, 'rejected: untrusted hostname')
                    log.info(peer[0] + ' is not a trusted hostname, closed connection')
                    self.send_error(writer, ValueError(peer[0] + ' is not a trusted hostname.'))
                    writer.close()
                    return
                log.debug(peer[0] + ' is a trusted hostname')
            else:
                if not await self.check_password(address, reader, writer):
                    return

        # check that the identity of the connecting device is valid
        identity = await self.check_identity(address, reader, writer)
        if not identity:
            return

        # the device is now connected, handle requests until it becomes disconnected
        self.database.insert(peer, 'connected')
        abrupt = await self.handle_requests(identity, address, reader, writer)
        if abrupt:
            return

        # disconnect from the device
        await writer.drain()
        writer.close()
        self.remove_peer(identity, address)

    async def check_password(self, address, reader, writer):
        """Request the password from the connected device.

        Parameters
        ----------
        address : :obj:`str`
            The address, ``'host:port'`` of the connected device.
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.

        Returns
        -------
        :obj:`bool`
            Whether the correct password was received.
        """
        self.send_request(writer, attribute='password', parameters={'hostname': HOSTNAME})
        password = await self.get_handshake_data(address, reader)

        if password is None:  # then the connection closed prematurely
            log.debug(address + ' correct password')
            return False

        if password == self.authentication:
            return True

        log.info(address + ' wrong password, closed connection')
        self.database.insert(address, 'rejected: wrong password')
        self.send_error(writer, ValueError('Wrong password'))
        writer.close()
        return False

    async def check_identity(self, address, reader, writer):
        """Request the identity from the connected device.

        Parameters
        ----------
        address : :obj:`str`
            The address, ``'host:port'`` of the connected device.
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.

        Returns
        -------
        :obj:`str`
            The type of the connection, either ``'client'`` or ``'service'``.
        """
        log.info(address + ' requesting identity')
        self.send_request(writer, attribute='identity')
        identity = await self.get_handshake_data(address, reader)

        if identity is None:  # then the connection closed prematurely
            return ''
        elif identity == 'client':
            # allow for a lazy way for a client to manually connect from a terminal, e.g. Putty
            identity = {'type': 'client'}

        try:
            if not isinstance(identity, dict):
                raise TypeError('Identification must be a valid JSON object. Got {!r}'.format(identity))

            type_ = identity['type'].lower()
            if type_ == 'client':
                self.clients.append(address)
                self.client_writers[address] = writer
                log.info(address + ' is a new client connection')
            elif type_ == 'service':
                self.services[identity['name']] = {
                    'attributes': identity['attributes'],
                    'address': identity.get('address', address),
                    'language': identity.get('language', 'Unknown'),
                    'os': identity.get('os', 'Unknown'),
                }
                self.service_writers[identity['name']] = (writer, address)
                log.info(address + ' is a new {} service'.format(identity['name']))
            else:
                raise TypeError(f'Unknown connection type "{type_}"')

            return type_

        except (TypeError, KeyError) as e:
            self.send_error(writer, e)
            writer.close()
            self.database.insert(address.split(':'), 'rejected: invalid identity')
            log.info(address + ' invalid identity, closed connection')
            return None

    async def get_handshake_data(self, address, reader):
        """Used by :meth:`check_password` and :meth`:check_identity`.

        Parameters
        ----------
        address : :obj:`str`
            The address, ``'host:port'`` of the connected device.
        reader : :class:`asyncio.StreamReader`
            The stream reader.

        Returns
        -------
        :obj:`None`, :obj:`str` or :obj:`dict`
            The data.
        """
        try:
            data = (await reader.readline()).decode(self.encoding).rstrip()
        except ConnectionAbortedError:
            # then most likely the connection was for a certificate request
            log.info(address + ' connection closed prematurely')
            self.database.insert(address.split(':'), 'closed prematurely')
            return None

        try:
            # ideally the response from the connected device will be in the required JSON format
            return json.loads(data)['return']
        except (json.JSONDecodeError, KeyError):
            # then just return the raw string (allowed for the password authentication)
            #
            # Perhaps the connection is through a terminal, e.g. Putty, so we can be a little
            # forgiving for not wanting to type everything that is required at this stage of
            # the handshake...
            return data

    async def handle_requests(self, identity, address, reader, writer):
        """Handle requests from the connected client.

        A client that is sending requests to the :class:`Manager` **MUST**
        send a JSON_ object with the following format::

            {
                'service': string (the name of the Service to process the request)
                'attribute': string (the name of a method or variable of the Service)
                'parameters': object (key-value pairs to be passed to the Service's method)
            }

        .. _JSON: http://www.json.org/

        Parameters
        ----------
        identity : :obj:`str`
            The type of the connection, either ``'client'`` or ``'service'``.
        address : :obj:`str`
            The address, ``'host:port'`` of the connected device.
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.

        Returns
        -------
        :obj:`bool`
            Whether the device disconnected abruptly (:obj:`True`), e.g., by
            pressing using CTRL+C, rather than sending a polite ``'__disconnect_'``
            request to disconnect itself from the Manager (:obj:`False`).
        """
        while True:

            try:
                line = await reader.readline()
            except ConnectionResetError:
                self.remove_peer(identity, address)
                return True  # then the device disconnected abruptly

            if not line:
                return True

            if self.debug or True:
                log.info(address + ' sent {!r}'.format(line))

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                # allow for a lazy way for a client connected via a terminal, e.g. Putty,
                # to request the identity of the Manager
                if line == b'identity\n':
                    data = {'service': None, 'attribute': 'identity', 'parameters': {}}
                else:
                    self.send_error(writer, e)
                    continue

            if 'return' in data:  # then data is a reply from a Service so send it to the Client
                # here address refers to the address of the Service
                for client_address, service_address in self.client_service_link.items():
                    if address == service_address:
                        self.client_writers[client_address].write(line)
                        break
            elif data['service'] is None:  # then requesting something from the Manager
                self.send_reply(writer, getattr(self, data['attribute'])(**data['parameters']))
            elif data['attribute'] == '__disconnect__':
                return False  # then the device requested to disconnect
            else:  # send the request to the appropriate Service
                try:
                    service, _ = self.service_writers[data['service']]
                except KeyError as e:
                    self.send_error(writer, e)
                else:
                    self.send_reply(writer, self.send_data(service, data))

    def remove_peer(self, identity, address):
        """Remove this peer from the registry of connected peers.

        Parameters
        ----------
        identity : :obj:`str`
            The type of the connection, either ``'client'`` or ``'service'``.
        address : :obj:`str`
            The address, ``'host:port'`` of the connected device.
        """
        if identity == 'client':
            try:
                index = self.clients.index(address)
                del self.clients[index]
                log.info(f'client {address} has been removed from the list')
            except ValueError:  # ideally this exception should never occur
                pass
        else:
            name = ''
            for service in self.services:
                if self.services[service]['address'] == address:
                    name = service
                    break
            if name:  # ideally there should be a service with this name
                del self.services[name]
                log.info(f'{name} service has been removed')
        log.info(address + ' connection closed')
        self.database.insert(address.split(':'), 'disconnected')

    async def shutdown_server(self):
        """Safely disconnect from all services and clients."""
        for address in self.client_writers:
            writer = self.client_writers[address]
            await writer.drain()
            writer.close()
            log.info(f'client {address} has been disconnected')
            self.database.insert(address.split(':'), 'disconnected')
        for name in self.service_writers:
            writer, address = self.service_writers[name]
            await writer.drain()
            writer.close()
            log.info(f'{name} service has been disconnected')
            self.database.insert(address.split(':'), 'disconnected')

    def identity(self):
        """:obj:`dict`: The metadata about the network manager."""
        return self._identity

    def link(self, client_address, service_name):
        """A request to link the Client to the Service.

        Parameters
        ----------
        client_address : :obj:`str`
            The address, ``'host:port'``, of the Client.
        service_name : :obj:`str`
            The name of the Service that the Client wants to link with.

        Returns
        -------
        :obj:`bool`
            Whether the link was successful. The only reason why the link
            would not be successful is if a Service called `service_name`
            is currently not connected to the Manager.
        """
        try:
            service_address = self.services[service_name]['address']
            # must use the client_address as the key since the address of a
            # Client is unique, whereas a Service can have multiple Clients
            # connected to it
            self.client_service_link[client_address] = service_address
            return True
        except KeyError as e:
            return False


def start_manager(auth, port, cert, key, key_password, database, debug):
    """Start the asynchronous network manager event loop."""

    # create the SSL context
    context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=cert, keyfile=key, password=key_password)

    log.info('loaded certificate {}'.format(os.path.basename(cert)))

    # load the connections database
    db = ConnectionsDatabase(database)
    log.info('loaded database {}'.format(db.path))

    if isinstance(auth, list):
        log.debug('using trusted hostname\'s for authentication')
    elif isinstance(auth, str):
        log.debug('using a password for authentication')

    # create the network manager
    manager = Manager(port, auth, db, debug)

    # create the event loop
    #
    # the documentation suggests that only the ProactorEventLoop supports SSL/TLS
    # connections but the default SelectorEventLoop seems to also work on Windows
    #
    # https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.AbstractEventLoop.create_connection
    loop = asyncio.get_event_loop()

    loop.set_debug(debug)

    server = loop.run_until_complete(
        asyncio.start_server(manager.new_connection, port=port, ssl=context, loop=loop)
    )

    log.info('network manager running on {}:{} using {}'.format(HOSTNAME, port, context.protocol.name))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info('CTRL+C keyboard interrupt received')
    finally:
        log.info('shutting down the network manager')
        if manager.client_writers or manager.service_writers:
            loop.run_until_complete(manager.shutdown_server())
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()
        log.info('event loop closed')
