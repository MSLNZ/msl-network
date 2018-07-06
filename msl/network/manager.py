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
from .constants import HOSTNAME
from .utils import parse_terminal_input
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
        port : :obj:`int`
            The port number that the Network :class:`Manager` is running on.
        password : :obj:`str` or :obj:`None`
            The password of the Network :class:`Manager`. Essentially, this can be a
            thought of as a single password that all :class:`~msl.network.client.Client`\'s
            and :class:`~msl.network.service.Service`\'s need to specify before the
            connection to the Network :class:`Manager` is successful. To use the `password` start
            the :class:`Manager` with the ``--auth-password`` flag.
        login : :obj:`bool` or :obj:`None`
            If :obj:`True` then the Network :class:`Manager` was started with the ``--auth-login`` flag
            and checks a users login credentials (the username and password) before a
            :class:`~msl.network.client.Client` or :class:`~msl.network.service.Service` successfully
            connects.
        hostnames : :obj:`list` of :obj:`str` or :obj:`None`
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
        debug : :obj:`bool`
            Whether debug logging messages are displayed.
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
        log.info('new connection request from ' + peer.address)
        self.connections_table.insert(peer, 'new connection request')

        # create a new attribute called 'peer' for the StreamReader and StreamWriter
        reader.peer = writer.peer = peer

        # check authentication
        if self.password is not None:
            if not await self.check_manager_password(reader, writer):
                return
        elif self.hostnames:
            log.info(self._network_name + ' verifying hostname of ' + peer.network_name)
            if peer.hostname not in self.hostnames:
                log.info(peer.hostname + ' is not a trusted hostname, closing connection')
                self.connections_table.insert(peer, 'rejected: untrusted hostname')
                self.send_error(writer, ValueError(peer.hostname + ' is not a trusted hostname.'), self._network_name)
                await self.close_writer(writer)
                return
            log.debug(peer.hostname + ' is a trusted hostname')
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
        :obj:`bool`
            Whether the login credentials are valid.
        """
        log.info(self._network_name + ' verifying login credentials from ' + writer.peer.network_name)
        log.debug(self._network_name + ' verifying login username from ' + writer.peer.network_name)
        self.send_request(writer, 'username', self._network_name)
        username = await self.get_handshake_data(reader)
        if not username:  # then the connection closed prematurely
            return False

        user = self.users_table.is_user_registered(username)
        if not user:
            log.error(reader.peer.network_name + ' sent an unregistered username, closing connection')
            self.connections_table.insert(reader.peer, 'rejected: unregistered username')
            self.send_error(writer, ValueError('Unregistered username'), self._network_name)
            await self.close_writer(writer)
            return False

        log.debug(self._network_name + ' verifying login password from ' + writer.peer.network_name)
        self.send_request(writer, 'password', username)
        password = await self.get_handshake_data(reader)

        if not password:  # then the connection closed prematurely
            return False

        if self.users_table.is_password_valid(username, password):
            log.debug(reader.peer.network_name + ' sent the correct login password')
            # writer.peer.is_admin points to the same location in memory so its value also gets updated
            reader.peer.is_admin = self.users_table.is_admin(username)
            return True

        log.info(reader.peer.network_name + ' sent the wrong login password, closing connection')
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
        :obj:`bool`
            Whether the correct password was received.
        """
        log.info(self._network_name + ' requesting password from ' + writer.peer.network_name)
        self.send_request(writer, 'password', self._network_name)
        password = await self.get_handshake_data(reader)

        if not password:  # then the connection closed prematurely
            return False

        if password == self.password:
            log.debug(reader.peer.network_name + ' sent the correct password')
            return True

        log.info(reader.peer.network_name + ' sent the wrong password, closing connection')
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
        log.info(self._network_name + ' requesting identity from ' + writer.peer.network_name)
        self.send_request(writer, 'identity')
        identity = await self.get_handshake_data(reader)

        if identity is None:  # then the connection closed prematurely (a certificate request?)
            return None
        elif isinstance(identity, str):
            identity = parse_terminal_input(identity)

        log.debug(reader.peer.network_name + ' has identity {}'.format(identity))

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
                    raise NameError('A {} service is already running on the Manager'.format(identity['name']))
                self.services[identity['name']] = {
                    'attributes': identity['attributes'],
                    'address': identity.get('address', reader.peer.address),
                    'language': identity.get('language', 'unknown'),
                    'os': identity.get('os', 'unknown'),
                }
                self.service_writers[identity['name']] = writer
                self.service_links[identity['name']] = set()
                log.info(reader.peer.network_name + ' is a new Service connection')
            else:
                raise TypeError('Unknown connection type "{}". Must be "client" or "service"'.format(typ))

            self.connections_table.insert(reader.peer, 'connected as a ' + typ)
            return typ

        except (TypeError, KeyError, NameError) as e:
            log.info(reader.peer.address + ' sent an invalid identity, closing connection')
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
            log.info(reader.peer.network_name + ' connection closed prematurely')
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
                log.debug(reader.peer.network_name + ' sent {} bytes'.format(len(line)))
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
                    log.info(reader.peer.network_name + ' was not able to deserialize the bytes')
                else:
                    try:
                        self.send_line(self.client_writers[data['requester']], line)
                    except KeyError:
                        log.info(data['requester'] + ' is no longer available to send the reply to')
            elif data['service'] == 'Manager':
                # then the Client is requesting something from the Manager
                if data['attribute'] == 'identity':
                    self.send_reply(writer, self.identity(), requester=reader.peer.address, uuid=data['uuid'])
                elif data['attribute'] == 'link':
                    try:
                        self.link(writer, data.get('uuid', ''), data['args'][0])
                    except Exception as e:
                        log.error(self._network_name + ' ' +  e.__class__.__name__ + ': ' + str(e))
                        self.send_error(writer, e, reader.peer.address, uuid=data.get('uuid', ''))
                else:
                    # the peer needs administrative rights to send any other request to the Manager
                    log.info('received an admin request from ' + reader.peer.network_name)
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
                        log.info('received shutdown request from ' + reader.peer.network_name)
                        self.loop.stop()
                        return
                    try:
                        # check for multiple dots "." in the name of the attribute
                        attrib = self
                        for item in data['attribute'].split('.'):
                            attrib = getattr(attrib, item)
                    except AttributeError as e:
                        log.error(self._network_name + ' AttributeError: ' + str(e))
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
                        log.error(self._network_name + ' ' + e.__class__.__name__ + ': ' + str(e))
                        self.send_error(writer, e, reader.peer.address)
            elif data['attribute'] == '__disconnect__':
                # then the device requested to disconnect
                return
            else:
                # send the request to the appropriate Service
                try:
                    data['requester'] = writer.peer.address
                    self.send_data(self.service_writers[data['service']], data)
                    log.info(writer.peer.address + ' sent a request to ' + data['service'])
                except KeyError:
                    msg = 'the "{}" Service is not connected to the Network Manager at {}'.format(
                        data['service'], self._network_name)
                    log.info(self._network_name + ' KeyError: ' + msg)
                    self.send_error(writer, KeyError(msg), reader.peer.address)

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
                log.info(writer.peer.network_name + ' has been removed from the registry')
            except KeyError:  # ideally this exception should never occur
                log.error(writer.peer.network_name + ' is not in the Client dictionaries')
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
                            ConnectionAbortedError('The "{}" service has been disconnected'.format(service)),
                            self._network_name,
                        )
                    try:
                        del self.service_links[service]
                        del self.services[service]
                        del self.service_writers[service]
                        log.info(writer.peer.network_name + ' service has been removed from the registry')
                    except KeyError:  # ideally this exception should never occur
                        log.error(writer.peer.network_name + ' is not in the Service dictionaries')
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
        log.info(writer.peer.network_name + ' connection closed')
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
        """:obj:`dict`: The :obj:`~msl.network.network.Network.identity` of
        the Network :class:`Manager`."""
        return self._identity

    def link(self, writer, uuid, service):
        """A request from a :class:`~msl.network.client.Client` to link it
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
            identity = self.services[service]
            self.service_links[service].add(writer.peer.address)
            log.info('linked ' + writer.peer.network_name + ' with ' + service)
            self.send_reply(writer, identity, requester=writer.peer.address, uuid=uuid)
        except KeyError:
            msg = service + ' service does not exist, could not link with ' + writer.peer.network_name
            log.info(msg)
            self.send_error(writer, KeyError(msg), writer.peer.address, uuid=uuid)

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
        args : :obj:`tuple`, optional
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

    def set_debug(self, boolean):
        """Set the debug mode of the Network :class:`Manager`.

        Parameters
        ----------
        boolean : :obj:`bool`
            Whether to enable or disable debug logging messages.
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
        self.hostname = self.domain.split('.')[0]
        if self.hostname == HOSTNAME:
            self.address = 'localhost:{}'.format(self.port)
            self.network_name = 'localhost:{}'.format(self.port)
        else:
            self.address = '{}:{}'.format(self.hostname, self.port)
            self.network_name = '{}:{}'.format(self.hostname, self.port)


def start(password, login, hostnames, port, cert, key, key_password, database, disable_tls, debug):
    """Start the asynchronous network manager event loop.

    .. attention::
        Not to be called directly. To be called from the command line.
    """

    # create the SSL context
    context = None
    if not disable_tls:
        context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=cert, keyfile=key, password=key_password)

    log.info('loaded certificate ' + cert)

    # load the connections table
    conn_table = ConnectionsTable(database=database)
    log.info('loaded the ' + conn_table.NAME + ' table from ' + conn_table.path)

    # load the auth_hostnames table
    hostnames_table = HostnamesTable(database=database)
    log.info('loaded the ' + hostnames_table.NAME + ' table from ' + hostnames_table.path)

    # load the auth_users table for the login credentials
    users_table = UsersTable(database=database)
    if login and not users_table.users():
        print('The Users Table is empty. You cannot use login credentials for authorisation.')
        print('See: msl-network users')
        return
    log.info('loaded the ' + users_table.NAME + ' table from ' + users_table.path)

    if hostnames:
        log.debug('using trusted hosts for authentication')
    elif password:
        log.debug('using a password for authentication')
    elif login:
        log.debug('using a login for authentication')
    else:
        log.debug('not using authentication')

    # create a new event loop, rather than using asyncio.get_event_loop()
    # (in case the Manager does not run in the threading._MainThread)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # create the network manager
    manager = Manager(port, password, login, hostnames, conn_table, users_table, hostnames_table, debug, loop)

    server = loop.run_until_complete(
        asyncio.start_server(manager.new_connection, port=port, ssl=context, loop=loop, limit=sys.maxsize)
    )

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

        for task in asyncio.Task.all_tasks(loop):
            task.cancel()

        log.info('closing the server')
        server.close()
        loop.run_until_complete(server.wait_closed())
        log.info('closing the event loop')
        loop.close()

        conn_table.close()
        users_table.close()
        hostnames_table.close()
