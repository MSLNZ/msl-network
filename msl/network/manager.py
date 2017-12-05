"""
An asynchronous Network Manager.
"""
import sys
import ssl
import socket
import asyncio
import logging
import platform

from .network import Network
from .json import deserialize
from .constants import HOSTNAME
from .utils import parse_terminal_input
from .database import ConnectionsTable, UsersTable

log = logging.getLogger(__name__)


class Manager(Network):

    def __init__(self, port, password, login, hostnames, connections_table, users_table, debug):
        """An asynchronous Network Manager.

        .. attention::
            Not to be instantiated directly. To be called from the command line.
        """
        self._debug = debug
        self._network_name = f'{HOSTNAME}:{port}'
        self.password = password
        self.login = login
        self.allowed_hostnames = hostnames
        self.connections_table = connections_table
        self.users_table = users_table
        self.clients = dict()
        self.services = dict()
        self.service_writers = dict()
        self.client_writers = dict()

        self._identity = {
            'hostname': HOSTNAME,
            'port': port,
            'attributes': {
                'identity': '() -> dict',
                'link': '(service:str) -> bool',
            },
            'language': 'Python ' + platform.python_version(),
            'os': '{} {} {}'.format(platform.system(), platform.release(), platform.machine()),
            'clients': self.clients,
            'services': self.services,
        }

    async def new_connection(self, reader, writer):
        """Receive a new connection request.

        To accept the new connection request, the following checks must be successful:

        1. The correct authentication reply is received.
        2. A correct :obj:`~msl.network.network.Network.identity` is received,
           i.e., is the connection from a :class:`~msl.network.client.Client` or
           :class:`~msl.network.service.Service`?

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.
        """
        peer = Peer(writer)  # a peer is either a Client or a Service
        log.info(f'new connection request from {peer.address}')
        self.connections_table.insert(peer, 'new connection request')

        # create a new attribute called 'peer' for the StreamReader and StreamWriter
        reader.peer = writer.peer = peer

        # check authentication
        if self.password is not None:
            if not await self.check_manager_password(reader, writer):
                return
        elif self.allowed_hostnames:
            log.info(f'{self._network_name} verifying hostname of {peer.network_name}')
            if peer.hostname not in self.allowed_hostnames:
                log.info(f'{peer.hostname} is not a trusted hostname, closing connection')
                self.connections_table.insert(peer, 'rejected: untrusted hostname')
                self.send_error(writer, ValueError(f'{peer.hostname} is not a trusted hostname.'), self._network_name)
                await self.close_writer(writer)
                return
            log.debug(f'{peer.hostname} is a trusted hostname')
        elif self.login:
            if not await self.check_user(reader, writer):
                return
        else:
            pass  # no authentication needed

        # check that the identity of the connecting device is valid
        id_type = await self.check_identity(reader, writer)
        if not id_type:
            return

        # the connection request from the device is now accepted
        # handle requests/replies from the device until it wants to disconnect from the Manager
        await self.handler(reader, writer)

        # disconnect the device from the Manager
        await self.close_writer(writer)
        self.remove_peer(id_type, writer)

    async def check_user(self, reader, writer):
        """Check the login credentials.

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.

        Returns
        -------
        :obj:`bool`
            Whether the login credentials are valid.
        """
        log.info(f'{self._network_name} verifying login credentials from {writer.peer.network_name}')
        log.debug(f'{self._network_name} verifying login username from {writer.peer.network_name}')
        self.send_request(writer, 'username', self._network_name)
        username = await self.get_handshake_data(reader)
        if not username:  # then the connection closed prematurely
            return False

        user = self.users_table.is_user_registered(username)
        if not user:
            log.error(f'{reader.peer.network_name} sent a unregistered username, closing connection')
            self.connections_table.insert(reader.peer, 'rejected: unregistered username')
            self.send_error(writer, ValueError('Unregistered username'), self._network_name)
            await self.close_writer(writer)
            return False

        log.debug(f'{self._network_name} verifying login password from {writer.peer.network_name}')
        self.send_request(writer, 'password', username)
        password = await self.get_handshake_data(reader)

        if not password:  # then the connection closed prematurely
            return False

        if self.users_table.is_password_valid(username, password):
            log.debug(f'{reader.peer.network_name} sent the correct login password')
            # writer.peer.is_admin points to the same location in memory so its value also gets updated
            reader.peer.is_admin = self.users_table.is_admin(username)
            return True

        log.info(f'{reader.peer.network_name} sent the wrong login password, closing connection')
        self.connections_table.insert(reader.peer, 'rejected: wrong login password')
        self.send_error(writer, ValueError('Wrong login password'), self._network_name)
        await self.close_writer(writer)
        return False

    async def check_manager_password(self, reader, writer):
        """Check the password from the connected device.

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.

        Returns
        -------
        :obj:`bool`
            Whether the correct password was received.
        """
        log.info(f'{self._network_name} requesting password from {writer.peer.network_name}')
        self.send_request(writer, 'password', self._network_name)
        password = await self.get_handshake_data(reader)

        if not password:  # then the connection closed prematurely
            return False

        if password == self.password:
            log.debug(f'{reader.peer.network_name} sent the correct password')
            return True

        log.info(f'{reader.peer.network_name} sent the wrong password, closing connection')
        self.connections_table.insert(reader.peer, 'rejected: wrong password')
        self.send_error(writer, ValueError('Wrong password'), self._network_name)
        await self.close_writer(writer)
        return False

    async def check_identity(self, reader, writer):
        """Check the :obj:`~msl.network.network.Network.identity` of the connected device.

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.

        Returns
        -------
        :obj:`str` or :obj:`None`
            If the identity check was successful then returns the connection type,
            either ``'client'`` or ``'service'``, otherwise returns :obj:`None`.
        """
        log.info(f'{self._network_name} requesting identity from {writer.peer.network_name}')
        self.send_request(writer, 'identity')
        identity = await self.get_handshake_data(reader)

        if identity is None:  # then the connection closed prematurely (a certificate request?)
            return None
        elif isinstance(identity, str):
            identity = parse_terminal_input(identity)

        log.debug(f'{reader.peer.network_name} has identity {identity}')

        try:
            # writer.peer.network_name points to the same location in memory so its value also gets updated
            reader.peer.network_name = f'{identity["name"]}[{reader.peer.address}]'

            typ = identity['type'].lower()
            if typ == 'client':
                self.clients[reader.peer.address] = {
                    'name': identity['name'],
                    'language': identity.get('language', 'unknown'),
                    'os': identity.get('os', 'unknown'),
                }
                # in the following line, "None" will eventually be the address
                # of the Service that the writer will be linked with
                self.client_writers[reader.peer.address] = [writer, None]
                log.info(f'{reader.peer.network_name} is a new Client connection')
            elif typ == 'service':
                if identity['name'] in self.services:
                    raise NameError(f'A {identity["name"]} service is already running on the Manager')
                self.services[identity['name']] = {
                    'attributes': identity['attributes'],
                    'address': identity.get('address', reader.peer.address),
                    'language': identity.get('language', 'unknown'),
                    'os': identity.get('os', 'unknown'),
                }
                self.service_writers[identity['name']] = writer
                log.info(f'{reader.peer.network_name} is a new Service connection')
            else:
                raise TypeError(f'Unknown connection type "{typ}". Must be "client" or "service"')

            self.connections_table.insert(reader.peer, f'connected as a {typ}')
            return typ

        except (TypeError, KeyError, NameError) as e:
            log.info(f'{reader.peer.address} sent an invalid identity, closing connection')
            self.connections_table.insert(reader.peer, 'rejected: invalid identity')
            self.send_error(writer, e, self._network_name)
            await self.close_writer(writer)
            return None

    async def get_handshake_data(self, reader):
        """Used by :meth:`check_password`, :meth:`check_identity` and :meth:`check_user`.

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.

        Returns
        -------
        :obj:`None`, :obj:`str` or :obj:`dict`
            The data.
        """
        try:
            data = (await reader.readline()).decode(self.encoding).rstrip()
        except (ConnectionAbortedError, ConnectionResetError):
            # then most likely the connection was for a certificate request
            log.info(f'{reader.peer.network_name} connection closed prematurely')
            self.connections_table.insert(reader.peer, 'connection closed prematurely')
            return None

        try:
            # ideally the response from the connected device will be in
            # the required JSON format
            return deserialize(data)['result']
        except:
            # however, if connecting via a terminal, e.g. Putty,  then it is convenient
            # to not manually type the JSON format and let the Manager parse the raw input
            return data

    async def handler(self, reader, writer):
        """Handle requests from the connected :class:`~msl.network.client.Client`\'s and
        replies from connected :class:`~msl.network.service.Service`\'s.

        A :class:`~msl.network.client.Client` that is sending requests to the Network
        :class:`Manager` **MUST** send a JSON_ object with the following format::

            {
                'service': string (the name of the Service to process the request)
                'attribute': string (the name of a method or variable of the Service)
                'args': array
                'kwargs': object (key-value pairs to be passed to the Service's method)
            }

        .. _JSON: http://www.json.org/

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.
        """
        while True:

            try:
                line = await reader.readline()
            except ConnectionResetError as e:
                return  # then the device disconnected abruptly

            if self._debug:
                log.debug(f'{reader.peer.network_name} sent {len(line)} bytes')
                if len(line) > self._max_print_size:
                    log.debug(line[:self._max_print_size//2] + b' ... ' + line[-self._max_print_size//2:])
                else:
                    log.debug(line)

            if not line:
                return

            try:
                data = deserialize(line)
            except Exception as e:
                data = parse_terminal_input(line.decode(self.encoding))
                if not data:
                    self.send_error(writer, e, reader.peer.address)
                    continue

            if 'result' in data:
                # then data is a reply from a Service so send it back to the Client
                if data['requester'] is None:
                    log.error(f'{reader.peer.network_name} was not able to deserialize the bytes')
                else:
                    try:
                        self.send_line(self.client_writers[data['requester']][0], line)
                    except KeyError:
                        log.error(f'{self._network_name} Client at {data["requester"]} is no longer available')
            elif data['service'] == 'Manager':
                # then the Client is requesting something from the Manager
                if data['attribute'] == 'identity':
                    self.send_reply(writer, self.identity(), requester=reader.peer.address, uuid=data['uuid'])
                elif data['attribute'] == 'link':
                    try:
                        self.link(writer, data.get('uuid', ''), data['args'][0])
                    except Exception as e:
                        log.error(f'{self._network_name} {e.__class__.__name__}: {e}')
                        self.send_error(writer, e, reader.peer.address)
                else:
                    # the peer needs administrative rights to send any other request to the Manager
                    log.info('received an admin request from {reader.peer.network_name}')
                    if not reader.peer.is_admin:
                        await self.check_user(reader, writer)
                        if not reader.peer.is_admin:
                            self.send_error(
                                writer,
                                ValueError('You must be an administrator to send this request to the Manager'),
                                reader.peer.address,
                            )
                            continue
                    if data['attribute'] == 'shutdown_manager':
                        # shutting down the Manager needs to be "awaited"
                        # so it is different from all other admin-type requests
                        log.info(f'received shutdown request from {reader.peer.network_name}')
                        await self.shutdown_manager()
                        return
                    # check for multiple dots "." in the name of the attribute
                    try:
                        attrib = self
                        for item in data['attribute'].split('.'):
                            attrib = getattr(attrib, item)
                    except AttributeError as e:
                        log.error(f'{self._network_name} AttributeError: {e}')
                        self.send_error(writer, e, reader.peer.address)
                        continue
                    # send the reply back to the Client
                    try:
                        if callable(attrib):
                            self.send_reply(writer, attrib(*data['args'], **data['kwargs']),
                                            requester=reader.peer.address)  # do not include the uuid
                        else:
                            self.send_reply(writer, attrib, requester=reader.peer.address)  # do not include the uuid
                    except Exception as e:
                        log.error(f'{self._network_name} {e.__class__.__name__}: {e}')
                        self.send_error(writer, e, reader.peer.address)
            elif data['attribute'] == '__disconnect__':
                # then the device requested to disconnect
                return
            else:
                # send the request to the appropriate Service
                try:
                    data['requester'] = writer.peer.address
                    self.send_data(self.service_writers[data['service']], data)
                except KeyError as e:
                    log.error(f'{self._network_name} KeyError: {e}')
                    self.send_error(writer, e, reader.peer.address)

    def remove_peer(self, id_type, writer):
        """Remove this peer from the registry of connected peers.

        Parameters
        ----------
        id_type : :obj:`str`
            The type of the connection, either ``'client'`` or ``'service'``.
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the peer.
        """
        if id_type == 'client':
            try:
                del self.clients[writer.peer.address]
                del self.client_writers[writer.peer.address]
                log.info(f'{writer.peer.network_name} has been removed from the registry')
            except KeyError:  # ideally this exception should never occur
                log.error(f'{writer.peer.network_name} is not in the clients dictionary')
        else:
            for service in self.services:
                if self.services[service]['address'] == writer.peer.address:
                    # notify all Clients that are linked with this Service
                    for w, service_address in self.client_writers.values():
                        if writer.peer.address == service_address:
                            self.send_error(
                                w,
                                ConnectionAbortedError(f'The {service} service has been disconnected'),
                                service_address,
                            )
                    del self.services[service]
                    del self.service_writers[service]
                    log.info(f'{writer.peer.network_name} service has been removed from the registry')
                    break

    async def close_writer(self, writer):
        """Close the connection to the :class:`asyncio.StreamWriter`.

        Log that the connection is closing, drains the writer and then
        closes the connection.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer to close.
        """
        try:
            await writer.drain()
            writer.close()
        except ConnectionResetError:
            pass
        log.info(f'{writer.peer.network_name} connection closed')
        self.connections_table.insert(writer.peer, 'disconnected')

    async def shutdown_manager(self):
        """Safely disconnect all :class:`~msl.network.service.Service`\'s and
        :class:`~msl.network.client.Client`\'s."""
        for writer, _ in self.client_writers.values():
            await self.close_writer(writer)
        for writer in self.service_writers.values():
            await self.close_writer(writer)
        asyncio.get_event_loop().stop()

    def identity(self):
        """:obj:`dict`: The :obj:`~msl.network.network.Network.identity` about
        the Network :class:`Manager`."""
        return self._identity

    def link(self, writer, uuid, service):
        """A request from the :class:`~msl.network.client.Client` to link it
        with a :class:`~msl.network.service.Service`.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the :class:`~msl.network.client.Client`.
        uuid : :obj:`str`
            The universally unique identifier of the request.
        service : :obj:`str`
            The name of the :class:`~msl.network.service.Service` that the
            :class:`~msl.network.client.Client` wants to link with.
        """
        try:
            address = self.services[service]['address']
            self.client_writers[writer.peer.address][1] = address
            log.info(f'linked {writer.peer.network_name} with {service}[{address}]')
            self.send_reply(writer, self.services[service], requester=writer.peer.address, uuid=uuid)
        except KeyError:
            msg = f'{service} service does not exist, could not link with {writer.peer.network_name}'
            log.info(msg)
            self.send_error(writer, KeyError(msg), writer.peer.address)

    def send_request(self, writer, attribute, *args, **kwargs):
        """Send a request to a :class:`~msl.network.client.Client` or a
        :class:`~msl.network.service.Service`.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the :class:`~msl.network.client.Client` or
            :class:`~msl.network.service.Service`.
        attribute : :obj:`str`
            The name of the method to call from the :class:`~msl.network.client.Client`
            or :class:`~msl.network.service.Service`.
        args : :obj:`dict`, optional
            The arguments that the `attribute` method requires.
        kwargs : :obj:`dict`, optional
            The key-value pairs that the `attribute` method requires.
        """
        self.send_data(writer, {
            'attribute': attribute,
            'args': args,
            'kwargs': kwargs,
            'requester': self._network_name,
            'uuid': '',
            'error': False,
        })


class Peer(object):

    def __init__(self, writer):
        """Metadata about a peer that is connected to the Network :class:`Manager`.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer for the peer.
        """
        self.is_admin = False
        self.ip_address, self.port = writer.get_extra_info('peername')[:2]
        self.domain = socket.getfqdn(self.ip_address)
        self.hostname = self.domain.split('.')[0]
        if self.hostname == HOSTNAME:
            self.address = f'localhost:{self.port}'
            self.network_name = f'localhost:{self.port}'
        else:
            self.address = f'{self.hostname}:{self.port}'
            self.network_name = f'{self.hostname}:{self.port}'


def start(password, login, hostnames, port, cert, key, key_password, database, debug):
    """Start the asynchronous network manager event loop.

    .. attention::
        Not to be called directly. To be called from the command line.
    """

    # create the SSL context
    context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=cert, keyfile=key, password=key_password)

    log.info(f'loaded certificate {cert}')

    # load the connections table
    conn_table = ConnectionsTable(database=database)
    log.info(f'loaded the {conn_table.NAME} table from {conn_table.path}')

    # load the users table for the login credentials
    users_table = UsersTable(database=database)
    if login and not users_table.users():
        print('The Users Table is empty. You cannot use login credentials for authorisation.')
        print('See: msl-network users')
        return
    log.info(f'loaded the {users_table.NAME} table from {users_table.path}')

    if hostnames:
        log.debug('using trusted hosts for authentication')
    elif password:
        log.debug('using a password for authentication')
    elif login:
        log.debug('using a login for authentication')
    else:
        log.debug('not using authentication')

    # create the network manager
    manager = Manager(port, password, login, hostnames, conn_table, users_table, debug)

    # create the event loop
    #
    # the documentation suggests that only the ProactorEventLoop supports SSL/TLS
    # connections but the default SelectorEventLoop seems to also work on Windows
    #
    # https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.AbstractEventLoop.create_connection
    loop = asyncio.get_event_loop()

    server = loop.run_until_complete(
        asyncio.start_server(manager.new_connection, port=port, ssl=context, loop=loop, limit=sys.maxsize)
    )

    log.info(f'Network Manager running on {HOSTNAME}:{port} using {context.protocol.name}')

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info('CTRL+C keyboard interrupt received')
    finally:
        log.info('shutting down the network manager')

        if manager.client_writers or manager.service_writers:
            loop.run_until_complete(manager.shutdown_manager())

        log.info('closing server')
        server.close()
        loop.run_until_complete(server.wait_closed())
        log.info('closing event loop')
        loop.close()
