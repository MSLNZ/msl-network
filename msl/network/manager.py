"""
The Network :class:`Manager`.
"""
import os
import sys
import ssl
import socket
import inspect
import asyncio
import logging
import platform
from datetime import datetime

from . import cryptography
from .network import Network
from .json import deserialize
from .service import (
    Service,
    parse_service_start_kwargs,
)
from .constants import (
    HOSTNAME,
    IS_WINDOWS,
    PORT,
    HOME_DIR,
    DATABASE,
    DISCONNECT_REQUEST,
)
from .database import (
    ConnectionsTable,
    UsersTable,
    HostnamesTable,
)
from .utils import (
    parse_terminal_input,
    ensure_root_path,
    _ipv4_regex,
)

log = logging.getLogger(__name__)


class Manager(Network):

    def __init__(self, port, password, login, hostnames, connections_table,
                 users_table, hostnames_table, debug, loop):
        """The Network :class:`Manager`.

        .. attention::
            Not to be instantiated directly. Start the Network :class:`Manager`
            from the command line. Run ``msl-network start --help`` from a terminal
            for more information.
        """
        self._debug = debug  # bool
        self._network_name = '{}:{}'.format(HOSTNAME, port)
        self.port = port  # int
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
        """Check the :class:`Manager`\\'s password from the connected device.

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
                log.info(repr(reader.peer.network_name) + ' is a new Client connection')
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
                log.info(repr(reader.peer.network_name) + ' is a new Service connection')
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
        """Handles requests from the connected :class:`~msl.network.client.Client`\\s and
        replies from the connected :class:`~msl.network.service.Service`\\s.

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
            elif data['attribute'] == DISCONNECT_REQUEST:
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
        Disconnect all :class:`~msl.network.service.Service`\\s and
        :class:`~msl.network.client.Client`\\s from the :class:`Manager`
        and then shut down the :class:`Manager`.
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
        """Send a request to a :class:`~msl.network.client.Client` or to a
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


def run_forever(*, port=PORT, auth_hostname=False, auth_login=False, auth_password=None,
                database=None, debug=False, disable_tls=False, certfile=None, keyfile=None,
                keyfile_password=None, logfile=None):
    """Start the event loop for the Network :class:`.Manager`.

    This is a blocking call and it will not return until the event loop of the :class:`.Manager`
    has stopped.

    .. versionadded:: 0.4

    Parameters
    ----------
    port : :class:`int`
        The port number to run the Network :class:`Manager` on.
    auth_hostname : :class:`bool`
        If :data:`True` then only connections from trusted hosts are allowed. If enabling
        `auth_hostname` then do not specify an `auth_password` and do not enable `auth_login`.
        Run ``msl-network hostname --help`` for more details.
    auth_login : :class:`bool`
        If :data:`True` then checks a users login credentials (the username and password)
        before a :class:`~msl.network.client.Client` or :class:`~msl.network.service.Service`
        successfully connects. If enabling `auth_login` then do not specify an `auth_password`
        and do not enable `auth_hostname`. Run ``msl-network user --help`` for more details.
    auth_password : :class:`str` or :data:`None`
        The password of the Network :class:`Manager`. Essentially, this can be a
        thought of as a single password that all :class:`~msl.network.client.Client`\\s
        and :class:`~msl.network.service.Service`\\s need to specify before the
        connection to the Network :class:`Manager` is successful. Can be a path to a file
        that contains the password on the first line in the file *(WARNING if the path is invalid*
        *then the value of the path becomes the password)*. If using an `auth_password`
        then do not enable `auth_login` nor `auth_hostname`.
    database : :class:`str` or :data:`None`
        The path to the sqlite3 database that contains the records for the following tables --
        :class:`.ConnectionsTable`, :class:`.HostnamesTable`, :class:`.UsersTable`. If
        :data:`None` then loads the default database.
    debug : :class:`bool`
        Whether :py:ref:`DEBUG <levels>` logging messages are displayed. On Windows, enabling
        debug mode also allows for the ``CTRL+C`` interrupt to stop the event loop.
    disable_tls : :class:`bool`
        Whether to disable using TLS for the protocol.
    certfile : :class:`str` or :data:`None`
        The path to the TLS certificate file. See :meth:`~ssl.SSLContext.load_cert_chain` for
        more details. Only required if using TLS.
    keyfile : :class:`str` or :data:`None`
        The path to the TLS key file. See :meth:`~ssl.SSLContext.load_cert_chain` for more details.
    keyfile_password : :class:`str` or :data:`None`
        The password to decrypt key. See :meth:`~ssl.SSLContext.load_cert_chain` for more details.
        Can be a path to a file that contains the password on the first line in the file
        *(WARNING if the path is invalid then the value of the path becomes the password).*
    logfile : :class:`str` or :data:`None`
        The file path to write logging messages to. If :data:`None` then use the default file path.
    """
    output = _create_manager_and_loop(
        port=port, auth_hostname=auth_hostname, auth_login=auth_login, auth_password=auth_password,
        database=database, debug=debug, disable_tls=disable_tls, certfile=certfile, keyfile=keyfile,
        keyfile_password=keyfile_password, logfile=logfile
    )

    if not output:
        return

    try:
        output['loop'].run_forever()
    except KeyboardInterrupt:
        log.info('CTRL+C keyboard interrupt received')
    finally:
        _cleanup(**output)


def run_services(*services, **kwargs):
    """This function starts the Network :class:`.Manager` and then starts the
    specified :class:`~msl.network.service.Service`\\s.

    This is a convenience function for running the Network :class:`.Manager`
    only when the specified :class:`~msl.network.service.Service`\\s are all
    connected to the :class:`.Manager`. Once all :class:`~msl.network.service.Service`\\s
    disconnect from the :class:`.Manager` then the :class:`.Manager` shuts down.

    This is a blocking call and it will not return until the event loop of the :class:`.Manager`
    has stopped.

    .. versionadded:: 0.4

    Parameters
    ----------
    services : :class:`~msl.network.service.Service`
        The :class:`~msl.network.service.Service`\\s to run on the :class:`.Manager`.
        Each :class:`~msl.network.service.Service` must be instantiated but not started.
        This :func:`run_services` function will start each :class:`~msl.network.service.Service`.
    kwargs
        The keyword arguments that can be passed to either :func:`run_forever` or to
        :meth:`~msl.network.service.Service.start`.

    Examples
    --------

    If you want to allow a :class:`~msl.network.client.Client` to be able to shut down a
    :class:`~msl.network.service.Service` then implement a public ``disconnect_service()``
    method on the :class:`~msl.network.service.Service`. For example,

    .. code-block:: python

        from msl.network import Service
        from msl.network.manager import run_services

        class DisconnectableService(Service):

            def disconnect_service(self):
                self._disconnect()

        class AddService(DisconnectableService):

            def add(self, a, b):
                return a + b

        class SubtractService(DisconnectableService):

            def subtract(self, a, b):
                return a - b

        run_services(AddService(), SubtractService())

    Since the ``_disconnect()`` method of a :class:`~msl.network.service.Service` is private
    (i.e., it starts with a ``_``), and a :class:`~msl.network.client.Client` cannot access
    private methods of a :class:`~msl.network.service.Service`, a :class:`~msl.network.client.Client`
    cannot call ``_disconnect()`` directly unless you intentionally make the public ``disconnect_service()``
    method available on the :class:`~msl.network.service.Service`.

    .. important::

       Do not rename the ``disconnect_service()`` method to be something that you prefer. The name
       ``disconnect_service`` is important.

    Then the :class:`~msl.network.client.Client` script could be

    .. code-block:: python

        from msl.network import connect

        cxn = connect()
        a = cxn.link('AddService')
        s = cxn.link('SubtractService')
        assert a.add(1, 2) == 3
        assert s.subtract(1, 2) == -1
        a.disconnect_service()
        s.disconnect_service()

    When this :class:`~msl.network.client.Client` script is finished running the Network
    :class:`.Manager` would have been shut down and the :func:`run_services` function
    will return.
    """
    if not services:
        msg = 'Warning... no services have been specified'
        log.error(msg)
        print(msg, file=sys.stderr)
        return

    for service in services:
        if not isinstance(service, Service):
            raise TypeError('All services must be of type {}'.format(Service))

    manager_kwargs = parse_run_forever_kwargs(**kwargs)
    service_kwargs = parse_service_start_kwargs(**kwargs)

    output = _create_manager_and_loop(**manager_kwargs)
    if not output:
        return

    async def start_service(s):
        await output['loop'].run_in_executor(None, lambda: s.start(**service_kwargs))

    tasks = [start_service(service) for service in services]

    try:
        output['loop'].run_until_complete(asyncio.gather(*tasks))
    except KeyboardInterrupt:
        log.info('CTRL+C keyboard interrupt received')
    finally:
        _cleanup(**output)


def parse_run_forever_kwargs(**kwargs):
    """From the specified keyword arguments only return those that are valid for
    :func:`~msl.network.manager.run_forever`.

    .. versionadded:: 0.4

    Parameters
    ----------
    kwargs
        Keyword arguments. All keyword arguments that are not part of the function
        signature for :func:`~msl.network.manager.run_forever` are silently ignored.

    Returns
    -------
    :class:`dict`
        Valid keyword arguments that can be passed to :func:`~msl.network.manager.run_forever`.
    """
    kws = {}
    for item in inspect.getfullargspec(run_forever).kwonlyargs:
        if item in kwargs:
            kws[item] = kwargs[item]

    # the manager uses an `auth_password` kwarg but a service uses a `password_manager` kwarg
    # however, these kwargs represent the same thing
    if 'password_manager' in kwargs and 'auth_password' not in kws:
        kws['auth_password'] = kwargs['password_manager']

    return kws


def _create_manager_and_loop(*, port=PORT, auth_hostname=False, auth_login=False, auth_password=None,
                             database=None, debug=False, disable_tls=False, certfile=None, keyfile=None,
                             keyfile_password=None, logfile=None):

    # set up logging -- FileHandler and StreamHandler
    if logfile is None:
        now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        logfile = os.path.join(HOME_DIR, 'logs', 'manager-{}.log'.format(now))
    ensure_root_path(logfile)

    # set the root logger level to DEBUG
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # add a FileHandler and it will always log at the debug level
    fh = logging.FileHandler(logfile, mode='w')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-8s] %(name)s - %(message)s'))
    root_logger.addHandler(fh)

    # add a StreamHandler and its log level can be decided from the command line
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.DEBUG if debug else logging.INFO)
    sh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-5s] %(name)s - %(message)s'))
    root_logger.addHandler(sh)

    # get the port number
    try:
        port = int(port)
    except ValueError:
        msg = 'ValueError: The port number must be an integer'
        log.error(msg)
        print(msg, file=sys.stderr)
        return

    # create the SSL context
    context = None
    if not disable_tls:
        # get the password to decrypt the private key
        if isinstance(keyfile_password, (list, tuple)):
            keyfile_password = ' '.join(keyfile_password)
        if keyfile_password is not None and os.path.isfile(keyfile_password):
            with open(keyfile_password, 'r') as fp:
                keyfile_password = fp.readline().strip()

        # get the path to the certificate and to the private key
        if certfile is None and keyfile is None:
            keyfile = cryptography.get_default_key_path()
            if not os.path.isfile(keyfile):
                cryptography.generate_key(path=keyfile, password=keyfile_password)
            certfile = cryptography.get_default_cert_path()
            if not os.path.isfile(certfile):
                cryptography.generate_certificate(path=certfile, key_path=keyfile, key_password=keyfile_password)
        elif certfile is None and keyfile is not None:
            # create (or overwrite) the default certificate to match the key
            certfile = cryptography.generate_certificate(key_path=keyfile, key_password=keyfile_password)
        elif certfile is not None and keyfile is None:
            pass  # assume that the certificate file also contains the private key

        context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile, keyfile=keyfile, password=keyfile_password)
        log.info('loaded certificate {!r}'.format(certfile))

    # get database file
    if database is not None:
        if not os.path.isfile(database):
            ensure_root_path(database)
    else:
        database = DATABASE

    # load the connections table
    conn_table = ConnectionsTable(database=database)
    log.info('loaded the {!r} table from {!r}'.format(conn_table.NAME, conn_table.path))

    # load the auth_hostnames table
    hostnames_table = HostnamesTable(database=database)
    log.info('loaded the {!r} table from {!r}'.format(hostnames_table.NAME, hostnames_table.path))

    # load the auth_users table for the login credentials
    users_table = UsersTable(database=database)
    log.info('loaded the {!r} table from {!r}'.format(users_table.NAME, users_table.path))

    # check which authentication method to use
    login, password, hostnames = None, None, None
    if not auth_password and not auth_hostname and not auth_login:
        # then no authentication is required for Clients or Services to connect to the Manager
        pass
    elif auth_password and not auth_hostname and not auth_login:
        # then the authentication is a password
        if isinstance(auth_password, (list, tuple)):
            password = ' '.join(auth_password)
        else:
            password = auth_password
        if os.path.isfile(password):
            with open(password, 'r') as fp:
                password = fp.readline().strip()
    elif not auth_password and auth_hostname and not auth_login:
        # then the authentication is based on a list of trusted hosts
        hostnames = hostnames_table.hostnames()
    elif not auth_password and not auth_hostname and auth_login:
        # then the authentication is based on the user's login information
        login = True
        if not users_table.usernames():
            users_table.close()
            conn_table.close()
            hostnames_table.close()
            msg = 'ValueError: The Users table is empty. No one could log in.\n' \
                  'To add a user to the Users table run the "msl-network user" command'
            log.error(msg)
            print(msg, file=sys.stderr)
            return
    else:
        users_table.close()
        conn_table.close()
        hostnames_table.close()
        msg = 'ValueError: Cannot specify multiple authentication methods'
        log.error(msg)
        print(msg, file=sys.stderr)
        return

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

    try:
        server = loop.run_until_complete(
            asyncio.start_server(manager.new_connection, port=port, ssl=context, loop=loop, limit=sys.maxsize)
        )
    except OSError as err:
        users_table.close()
        conn_table.close()
        hostnames_table.close()
        log.error(err)
        print(err, file=sys.stderr)
        return

    # https://bugs.python.org/issue23057
    # enable this hack only in debug mode and only on Windows
    if debug and IS_WINDOWS:
        async def wakeup():
            while True:
                await asyncio.sleep(1)
        loop.create_task(wakeup())

    state = 'ENABLED' if context else 'DISABLED'
    log.info('Network Manager running on {}:{} (TLS {})'.format(HOSTNAME, port, state))

    return {
        'manager': manager,
        'loop': loop,
        'server': server,
        'db_tables': [conn_table, hostnames_table, users_table]
    }


def _cleanup(manager, loop, server, db_tables):
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

    log.info('closing the connection server')
    server.close()
    loop.run_until_complete(server.wait_closed())
    log.info('closing the event loop')
    loop.close()

    # close the database tables
    for table in db_tables:
        table.close()
