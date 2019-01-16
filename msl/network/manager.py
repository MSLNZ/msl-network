"""
The Network :class:`Manager`.
"""
import sys
import ssl
import socket
import asyncio
import logging
import platform

from .network import Network
from .json import deserialize
from .constants import HOSTNAME, IS_WINDOWS
from .utils import parse_terminal_input, _ipv4_regex
from .database import ConnectionsTable, UsersTable, HostnamesTable

log = logging.getLogger(__name__)


class Manager(Network):

    def __init__(self, port, password, login, hostnames, connections_table,
                 users_table, hostnames_table, debug, loop):
        """The Network :class:`Manager`.

        .. attention::
            Not to be instantiated directly. Start the Network :class:`Manager`
            from the command line. Run ``msl-network start --help`` from a terminal
            for more information.

        Parameters
        ----------
        port : :class:`int`
            The port number that the Network :class:`Manager` is running on.
        password : :class:`str` or :data:`None`
            The password of the Network :class:`Manager`. Essentially, this can be a
            thought of as a single password that all :class:`~msl.network.client.Client`\'s
            and :class:`~msl.network.service.Service`\'s need to specify before the
            connection to the Network :class:`Manager` is successful. To use the `password` start
            the :class:`Manager` with the ``--auth-password`` flag.
        login : :class:`bool` or :data:`None`
            If :data:`True` then the Network :class:`Manager` was started with the ``--auth-login`` flag
            and checks a users login credentials (the username and password) before a
            :class:`~msl.network.client.Client` or :class:`~msl.network.service.Service` successfully
            connects.
        hostnames : :class:`list` of :class:`str` or :data:`None`
            A list of trusted hostnames of devices that can connect to the Network
            :class:`Manager` (only if the Network :class:`Manager` was started using the
            ``--auth-hostname`` flag as the authentication procedure).
        connections_table : :class:`~msl.network.database.ConnectionsTable`
            The table in the database that keeps the records for the devices that connected
            to the Network :class:`Manager`.
        users_table : :class:`~msl.network.database.UsersTable`
            The table in the database that keeps the records of the users that can connect
            to the Network :class:`Manager`.
        hostnames_table : :class:`~msl.network.database.HostnamesTable`
            The table in the database that keeps the records of the trusted hostnames that
            can connect to the Network :class:`Manager`.
        debug : :class:`bool`
            Whether :py:ref:`DEBUG <levels>` logging messages are displayed.
        loop : :class:`asyncio.AbstractEventLoop`
            The event loop that the Network :class:`Manager` is running in.
        """
        self._debug = debug
        self._network_name = '{}:{}'.format(HOSTNAME, port)
        self.port = port
        self.loop = loop  # asyncio.AbstractEventLoop
        self.password = password  # string or None
        self.login = login  # boolean or None
        self.hostnames = hostnames  # list of trusted hostnames or None
        self.connections_table = connections_table  # msl.network.database.ConnectionsTable object
        self.users_table = users_table  # msl.network.database.UsersTable object
        self.hostnames_table = hostnames_table  # msl.network.database.HostnamesTable object
        self.clients = dict()  # keys: Client address, values: the identity dictionary
        self.services = dict()  # keys: Service name, values: the identity dictionary
        self.service_writers = dict()  # keys: Service name, values: StreamWriter of the Service
        self.service_links = dict()  # keys: Service name, values: set() of StreamWriter's of the linked Clients
        self.client_writers = dict()  # keys: Client address, values: StreamWriter of the Client

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
        log.info('new connection request from {!r}'.format(peer.address))
        self.connections_table.insert(peer, 'new connection request')

        # create a new attribute called 'peer' for the StreamReader and StreamWriter
        reader.peer = writer.peer = peer

        # check authentication
        if self.password is not None:
            if not await self.check_manager_password(reader, writer):
                return
        elif self.hostnames:
            log.info('{!r} verifying hostname of {!r}'.format(self._network_name, peer.network_name))
            if peer.hostname not in self.hostnames:
                log.info('{!r} is not a trusted hostname, closing connection'.format(peer.hostname))
                self.connections_table.insert(peer, 'rejected: untrusted hostname')
                self.send_error(writer, ValueError('{!r} is not a trusted hostname'.format(peer.hostname)), self._network_name)
                await self.close_writer(writer)
                return
            log.debug('{!r} is a trusted hostname'.format(peer.hostname))
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
        """Check the login credentials of a user.

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.

        Returns
        -------
        :class:`bool`
            Whether the login credentials are valid.
        """
        log.info('{!r} verifying login credentials from {!r}'.format(self._network_name, writer.peer.network_name))
        log.debug('{!r} verifying login username from {!r}'.format(self._network_name, writer.peer.network_name))
        self.send_request(writer, 'username', self._network_name)
        username = await self.get_handshake_data(reader)
        if not username:  # then the connection closed prematurely
            log.info('{!r} connection closed before receiving the username'.format(reader.peer.network_name))
            self.connections_table.insert(reader.peer, 'connection closed before receiving the username')
            return False

        user = self.users_table.is_user_registered(username)
        if not user:
            log.error('{!r} sent an unregistered username, closing connection'.format(reader.peer.network_name))
            self.connections_table.insert(reader.peer, 'rejected: unregistered username')
            self.send_error(writer, ValueError('Unregistered username'), self._network_name)
            await self.close_writer(writer)
            return False

        log.debug('{!r} verifying login password from {!r}'.format(self._network_name, writer.peer.network_name))
        self.send_request(writer, 'password', username)
        password = await self.get_handshake_data(reader)

        if not password:  # then the connection closed prematurely
            log.info('{!r} connection closed before receiving the password'.format(reader.peer.network_name))
            self.connections_table.insert(reader.peer, 'connection closed before receiving the password')
            return False

        if self.users_table.is_password_valid(username, password):
            log.debug('{!r} sent the correct login password'.format(reader.peer.network_name))
            # writer.peer.is_admin points to the same location in memory so its value also gets updated
            reader.peer.is_admin = self.users_table.is_admin(username)
            return True

        log.info('{!r} sent the wrong login password, closing connection'.format(reader.peer.network_name))
        self.connections_table.insert(reader.peer, 'rejected: wrong login password')
        self.send_error(writer, ValueError('Wrong login password'), self._network_name)
        await self.close_writer(writer)
        return False

    async def check_manager_password(self, reader, writer):
        """Check the :class:`Manager`\'s password from the connected device.

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.

        Returns
        -------
        :class:`bool`
            Whether the correct password was received.
        """
        log.info('{!r} requesting password from {!r}'.format(self._network_name, writer.peer.network_name))
        self.send_request(writer, 'password', self._network_name)
        password = await self.get_handshake_data(reader)
        if not password:  # then the connection closed prematurely
            log.info('{!r} connection closed before receiving the password'.format(reader.peer.network_name))
            self.connections_table.insert(reader.peer, 'connection closed before receiving the password')
            return False

        if password == self.password:
            log.debug('{!r} sent the correct password'.format(reader.peer.network_name))
            return True

        log.info('{!r} sent the wrong Manager password, closing connection'.format(reader.peer.network_name))
        self.connections_table.insert(reader.peer, 'rejected: wrong Manager password')
        self.send_error(writer, ValueError('Wrong Manager password'), self._network_name)
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
        :class:`str` or :data:`None`
            If the identity check was successful then returns the connection type,
            either ``'client'`` or ``'service'``, otherwise returns :data:`None`.
        """
        log.info('{!r} requesting identity from {!r}'.format(self._network_name, writer.peer.network_name))
        self.send_request(writer, 'identity')
        identity = await self.get_handshake_data(reader)

        if identity is None:  # then the connection closed prematurely (a certificate request?)
            return None
        elif isinstance(identity, str):
            identity = parse_terminal_input(identity)

        log.debug('{!r} has identity {}'.format(reader.peer.network_name, identity))

        try:
            # writer.peer.network_name points to the same location in memory so its value also gets updated
            reader.peer.network_name = '{}[{}]'.format(identity['name'], reader.peer.address)

            typ = identity['type'].lower()
            if typ == 'client':
                self.clients[reader.peer.address] = {
                    'name': identity['name'],
                    'language': identity.get('language', 'unknown'),
                    'os': identity.get('os', 'unknown'),
                }
                self.client_writers[reader.peer.address] = writer
                log.info(reader.peer.network_name + ' is a new Client connection')
            elif typ == 'service':
                if identity['name'] in self.services:
                    raise NameError('A {!r} service is already running on the Manager'.format(identity['name']))
                self.services[identity['name']] = {
                    'attributes': identity['attributes'],
                    'address': identity.get('address', reader.peer.address),
                    'language': identity.get('language', 'unknown'),
                    'os': identity.get('os', 'unknown'),
                    'max_clients': identity.get('max_clients', -1),
                }
                self.service_writers[identity['name']] = writer
                self.service_links[identity['name']] = set()
                log.info(reader.peer.network_name + ' is a new Service connection')
            else:
                raise TypeError('Unknown connection type {!r}. Must be "client" or "service"'.format(typ))

            self.connections_table.insert(reader.peer, 'connected as a ' + typ)
            return typ

        except (TypeError, KeyError, NameError) as e:
            log.info('{!r} sent an invalid identity, closing connection'.format(reader.peer.address))
            self.connections_table.insert(reader.peer, 'rejected: invalid identity')
            self.send_error(writer, e, self._network_name)
            await self.close_writer(writer)
            return None

    async def get_handshake_data(self, reader):
        """Used by :meth:`check_manager_password`, :meth:`check_identity` and :meth:`check_user`.

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.

        Returns
        -------
        :data:`None`, :class:`str` or :class:`dict`
            The data.
        """
        try:
            data = (await reader.readline()).decode(self.encoding).rstrip()
        except (ConnectionAbortedError, ConnectionResetError, UnicodeDecodeError):
            # then most likely the connection was for a certificate request, or,
            # the connection is trying to use a certificate and the Manage has TLS disabled
            log.info('{!r} connection closed prematurely'.format(reader.peer.network_name))
            self.connections_table.insert(reader.peer, 'connection closed prematurely')
            return None

        try:
            # ideally the response from the connected device will be in
            # the required JSON format
            return deserialize(data)['result']
        except:
            # however, if connecting via a terminal, e.g. openssl s_client,  then it is convenient
            # to not manually type the JSON format and let the Manager parse the raw input
            return data

    async def handler(self, reader, writer):
        """Handle requests from the connected :class:`~msl.network.client.Client`\'s and
        replies from connected :class:`~msl.network.service.Service`\'s.

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
                log.debug('{!r} sent {} bytes'.format(reader.peer.network_name, len(line)))
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
                    log.info('{!r} was not able to deserialize the bytes'.format(reader.peer.network_name))
                else:
                    try:
                        self.send_line(self.client_writers[data['requester']], line)
                    except KeyError:
                        log.info('{!r} is no longer available to send the reply to'.format(data['requester']))
            elif data['service'] == 'Manager':
                # then the Client is requesting something from the Manager
                if data['attribute'] == 'identity':
                    self.send_reply(writer, self.identity(), requester=reader.peer.address, uuid=data['uuid'])
                elif data['attribute'] == 'link':
                    try:
                        self.link(writer, data.get('uuid', ''), data['args'][0])
                    except Exception as e:
                        log.error('{!r} {}: {}'.format(self._network_name, e.__class__.__name__, e))
                        self.send_error(writer, e, reader.peer.address, uuid=data.get('uuid', ''))
                else:
                    # the peer needs administrative rights to send any other request to the Manager
                    log.info('received an admin request from {!r}'.format(reader.peer.network_name))
                    if not reader.peer.is_admin:
                        await self.check_user(reader, writer)
                        if not reader.peer.is_admin:
                            self.send_error(
                                writer,
                                ValueError('You must be an administrator to send this request to the Manager'),
                                reader.peer.address
                            )
                            continue
                    # the peer is an administrator, so execute the request
                    if data['attribute'] == 'shutdown_manager':
                        log.info('received shutdown request from {!r}'.format(reader.peer.network_name))
                        self.loop.stop()
                        return
                    try:
                        # check for multiple dots "." in the name of the attribute
                        attrib = self
                        for item in data['attribute'].split('.'):
                            attrib = getattr(attrib, item)
                    except AttributeError as e:
                        log.error('{!r} AttributeError: {}'.format(self._network_name, e))
                        self.send_error(writer, e, reader.peer.address)
                        continue
                    try:
                        # send the reply back to the Client
                        if callable(attrib):
                            reply = attrib(*data['args'], **data['kwargs'])
                        else:
                            reply = attrib
                        # do not include the uuid in the reply
                        self.send_reply(writer, reply, requester=reader.peer.address)
                    except Exception as e:
                        log.error('{!r} {}: {}'.format(self._network_name, e.__class__.__name__, e))
                        self.send_error(writer, e, reader.peer.address)
            elif data['attribute'] == '__disconnect__':
                # then the device requested to disconnect
                return
            else:
                # send the request to the appropriate Service
                try:
                    data['requester'] = writer.peer.address
                    self.send_data(self.service_writers[data['service']], data)
                    log.info('{!r} sent a request to {!r}'.format(writer.peer.address, data['service']))
                except KeyError:
                    msg = 'the {!r} Service is not connected to the Network Manager at {!r}'.format(
                        data['service'], self._network_name)
                    log.info('{!r} KeyError: {}'.format(self._network_name, msg))
                    self.send_error(writer, KeyError(msg), reader.peer.address)

    def remove_peer(self, id_type, writer):
        """Remove this peer from the registry of connected peers.

        Parameters
        ----------
        id_type : :class:`str`
            The type of the connection, either ``'client'`` or ``'service'``.
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the peer.
        """
        if id_type == 'client':
            try:
                del self.clients[writer.peer.address]
                del self.client_writers[writer.peer.address]
                log.info('{!r} has been removed from the registry'.format(writer.peer.network_name))
            except KeyError:  # ideally this exception should never occur
                log.error('{!r} is not in the Client dictionaries'.format(writer.peer.network_name))

            # remove this Client from all Services that it was linked with
            for service_name, client_addresses in self.service_links.items():
                if writer.peer.address in client_addresses:
                    self.service_links[service_name].remove(writer.peer.address)
        else:
            for service in self.services:
                if self.services[service]['address'] == writer.peer.address:
                    # notify all Clients that are linked with this Service
                    for client_address in self.service_links[service]:
                        try:
                            client_writer = self.client_writers[client_address]
                        except KeyError:  # in case the Client already disconnected
                            continue
                        self.send_error(
                            client_writer,
                            ConnectionAbortedError('The {!r} service has been disconnected'.format(service)),
                            self._network_name,
                        )
                    try:
                        del self.service_links[service]
                        del self.services[service]
                        del self.service_writers[service]
                        log.info('{!r} service has been removed from the registry'.format(writer.peer.network_name))
                    except KeyError:  # ideally this exception should never occur
                        log.error('{!r} is not in the Service dictionaries'.format(writer.peer.network_name))
                    finally:
                        # must break from the iteration, otherwise will get
                        # RuntimeError: dictionary changed size during iteration
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
        log.info('{!r} connection closed'.format(writer.peer.network_name))
        self.connections_table.insert(writer.peer, 'disconnected')

    async def shutdown_manager(self):
        """
        Disconnect all :class:`~msl.network.service.Service`\'s and
        :class:`~msl.network.client.Client`\'s from the :class:`Manager`
        and then shutdown the :class:`Manager`.
        """
        # convert the dict_values to a list since we are modifying the dictionary in remove_peer()
        for writer in list(self.client_writers.values()):
            await self.close_writer(writer)
            self.remove_peer('client', writer)
        for writer in list(self.service_writers.values()):
            await self.close_writer(writer)
            self.remove_peer('service', writer)

    def identity(self):
        """:class:`dict`: The :obj:`~msl.network.network.Network.identity` of
        the Network :class:`Manager`."""
        return self._identity

    def link(self, writer, uuid, service):
        """A request from a :class:`~msl.network.client.Client` to link it
        with a :class:`~msl.network.service.Service`.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the :class:`~msl.network.client.Client`.
        uuid : :class:`str`
            The universally unique identifier of the request.
        service : :class:`str`
            The name of the :class:`~msl.network.service.Service` that the
            :class:`~msl.network.client.Client` wants to link with.
        """
        try:
            identity = self.services[service]
        except KeyError:
            msg = '{!r} service does not exist, could not link with {!r}'.format(service, writer.peer.network_name)
            log.info(msg)
            self.send_error(writer, KeyError(msg), writer.peer.address, uuid=uuid)
        else:
            if writer.peer.address in self.service_links[service]:
                # a Client wants to re-link with the same Service
                log.info('re-linked {!r} with {!r}'.format(writer.peer.network_name, service))
                self.send_reply(writer, identity, requester=writer.peer.address, uuid=uuid)
            elif identity['max_clients'] <= 0 or len(self.service_links[service]) < identity['max_clients']:
                self.service_links[service].add(writer.peer.address)
                log.info('linked {!r} with {!r}'.format(writer.peer.network_name, service))
                self.send_reply(writer, identity, requester=writer.peer.address, uuid=uuid)
            else:
                msg = 'The maximum number of Clients are already linked with {!r}. ' \
                      'The linked Clients are {}'.format(service, self.service_links[service])
                log.info(msg)
                self.send_error(writer, PermissionError(msg), writer.peer.address, uuid=uuid)

    def send_request(self, writer, attribute, *args, **kwargs):
        """Send a request to a :class:`~msl.network.client.Client` or a
        :class:`~msl.network.service.Service`.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the :class:`~msl.network.client.Client` or
            :class:`~msl.network.service.Service`.
        attribute : :class:`str`
            The name of the method to call from the :class:`~msl.network.client.Client`
            or :class:`~msl.network.service.Service`.
        args : :class:`tuple`, optional
            The arguments that the `attribute` method requires.
        kwargs : :class:`dict`, optional
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

    def set_debug(self, boolean):
        """Set the :py:ref:`DEBUG <levels>` mode of the Network :class:`Manager`.

        Parameters
        ----------
        boolean : :class:`bool`
            Whether to enable or disable :py:ref:`DEBUG <levels>` logging messages.
        """
        self._debug = bool(boolean)


class Peer(object):

    def __init__(self, writer):
        """Metadata about a peer that is connected to the Network :class:`Manager`.

        .. attention::
            Not to be called directly. To be called when the Network :class:`Manager`
            receives a :meth:`~Manager.new_connection` request.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer for the peer.
        """
        self.is_admin = False
        self.ip_address, self.port = writer.get_extra_info('peername')[:2]
        self.domain = socket.getfqdn(self.ip_address)

        if _ipv4_regex.search(self.domain):
            self.hostname = self.domain
        else:
            self.hostname = self.domain.split('.')[0]

        if self.hostname == HOSTNAME:
            self.address = 'localhost:{}'.format(self.port)
            self.network_name = 'localhost:{}'.format(self.port)
        else:
            self.address = '{}:{}'.format(self.hostname, self.port)
            self.network_name = '{}:{}'.format(self.hostname, self.port)


def start(password, login, hostnames, port, cert, key, key_password, database, disable_tls, debug):
    """Start the Network :class:`.Manager`\'s event loop.

    .. attention::
        Not to be called directly. To be called from the command line.
    """

    # create the SSL context
    context = None
    if not disable_tls:
        context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=cert, keyfile=key, password=key_password)
        log.info('loaded certificate {!r}'.format(cert))

    # load the connections table
    conn_table = ConnectionsTable(database=database)
    log.info('loaded the {!r} table from {!r}'.format(conn_table.NAME, conn_table.path))

    # load the auth_hostnames table
    hostnames_table = HostnamesTable(database=database)
    log.info('loaded the {!r} table from {!r}'.format(hostnames_table.NAME, hostnames_table.path))

    # load the auth_users table for the login credentials
    users_table = UsersTable(database=database)
    if login and not users_table.users():
        print('The Users Table is empty. You cannot use login credentials for authorisation.')
        print('See: msl-network users')
        return
    log.info('loaded the {!r} table from {!r}'.format(users_table.NAME, users_table.path))

    if hostnames:
        log.info('using trusted hosts for authentication')
    elif password:
        log.info('using a password for authentication')
    elif login:
        log.info('using a login for authentication')
    else:
        log.info('not using authentication')

    # create a new event loop, rather than using asyncio.get_event_loop()
    # (in case the Manager does not run in the threading._MainThread)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # create the network manager
    manager = Manager(port, password, login, hostnames, conn_table, users_table, hostnames_table, debug, loop)

    server = loop.run_until_complete(
        asyncio.start_server(manager.new_connection, port=port, ssl=context, loop=loop, limit=sys.maxsize)
    )

    # https://bugs.python.org/issue23057
    # enable this hack only in debug mode and only on Windows
    if debug and IS_WINDOWS:
        async def wakeup():
            while True:
                await asyncio.sleep(1)
        loop.create_task(wakeup())

    state = 'ENABLED' if context else 'DISABLED'
    log.info('Network Manager running on {}:{} (TLS {})'.format(HOSTNAME, port, state))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info('CTRL+C keyboard interrupt received')
    finally:
        log.info('shutting down the network manager')

        if manager.client_writers or manager.service_writers:
            loop.run_until_complete(manager.shutdown_manager())

        if sys.version_info >= (3, 7):
            all_tasks = asyncio.all_tasks
        else:
            # From the docs:
            #  This method is deprecated and will be removed in Python 3.9.
            #  Use the asyncio.all_tasks() function instead.
            all_tasks = asyncio.Task.all_tasks

        for task in all_tasks(loop=loop):
            task.cancel()

        log.info('closing the server')
        server.close()
        loop.run_until_complete(server.wait_closed())
        log.info('closing the event loop')
        loop.close()

        conn_table.close()
        users_table.close()
        hostnames_table.close()
