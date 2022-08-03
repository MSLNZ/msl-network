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
    filter_service_start_kwargs,
)
from .constants import (
    HOSTNAME,
    PORT,
    HOME_DIR,
    DATABASE,
    DISCONNECT_REQUEST,
    NETWORK_MANAGER_RUNNING_PREFIX,
    NOTIFICATION_UID,
    SHUTDOWN_MANAGER,
    LOCALHOST_ALIASES,
    KEY_DIR,
    CERT_DIR,
)
from .database import (
    ConnectionsTable,
    UsersTable,
    HostnamesTable,
)
from .utils import (
    logger,
    parse_terminal_input,
    ensure_root_path,
    _ipv4_regex,
)


class Manager(Network):

    def __init__(self, port, password, login, hostnames, connections_table,
                 users_table, hostnames_table, loop):
        """The Network :class:`Manager`.

        .. attention::
            Not to be instantiated directly. Start the Network :class:`Manager`
            from the command line. Run ``msl-network start --help`` from a terminal
            for more information.
        """
        super(Manager, self).__init__()
        self._network_name = f'Manager[{HOSTNAME}:{port}]'
        self._loop = loop  # asyncio.AbstractEventLoop
        self.port = port  # int
        self.password = password  # string or None
        self.login = login  # boolean or None
        self.hostnames = hostnames  # list of trusted hostnames or None
        self.connections_table = connections_table  # msl.network.database.ConnectionsTable object
        self.users_table = users_table  # msl.network.database.UsersTable object
        self.hostnames_table = hostnames_table  # msl.network.database.HostnamesTable object
        self.clients = dict()  # keys: Client network name, values: the identity dictionary
        self.services = dict()  # keys: Service name, values: the identity dictionary
        self.service_writers = dict()  # keys: Service name, values: StreamWriter of the Service
        self.service_links = dict()  # keys: Service name, values: set() of network name's of the linked Clients
        self.client_writers = dict()  # keys: Client network name, values: StreamWriter of the Client

        self._identity = {
            'hostname': HOSTNAME,
            'port': port,
            'attributes': {
                'identity': '() -> dict',
                'link': '(service: str) -> bool',
            },
            'language': f'Python {platform.python_version()}',
            'os': f'{platform.system()} {platform.release()} {platform.machine()}',
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
        logger.info('new connection request from %s', peer.address)
        self.connections_table.insert(peer, 'new connection request')

        # create a new attribute called 'peer' for the StreamReader and StreamWriter
        reader.peer = writer.peer = peer

        # check authentication
        if self.password is not None:
            if not await self.check_manager_password(reader, writer):
                return
        elif self.hostnames:
            logger.info('%s verifying hostname of %r', self, peer.address)
            if peer.hostname not in self.hostnames:
                logger.info('%r is not a trusted hostname, closing connection', peer.hostname)
                self.connections_table.insert(peer, 'rejected: untrusted hostname')
                await self._write_error(
                    ValueError(f'{peer.hostname!r} is not a trusted hostname'),
                    requester=self._network_name,
                    writer=writer
                )
                await self.close_writer(writer)
                return
            logger.debug('%r is a trusted hostname', peer.hostname)
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
        await self.remove_peer(id_type, writer)

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
        logger.info('%s verifying login credentials from %s', self, writer.peer.address)  # noqa
        logger.debug('%s verifying login username from %s', self, writer.peer.address)  # noqa
        await self.write_request(writer, 'username', self._network_name)
        username = await self.get_handshake_data(reader)
        if not username:  # then the connection closed prematurely
            logger.info('%s connection closed before receiving the username', reader.peer.address)  # noqa
            self.connections_table.insert(reader.peer, 'connection closed before receiving the username')  # noqa
            return False

        user = self.users_table.is_user_registered(username)
        if not user:
            logger.error('%s sent an unregistered username, closing connection', reader.peer.address)  # noqa
            self.connections_table.insert(reader.peer, 'rejected: unregistered user')  # noqa
            await self._write_error(ValueError('Unregistered user'), requester=self._network_name, writer=writer)
            await self.close_writer(writer)
            return False

        logger.debug('%s verifying login password from %s', self, writer.peer.address)  # noqa
        await self.write_request(writer, 'password', username)
        password = await self.get_handshake_data(reader)

        if not password:  # then the connection closed prematurely
            logger.info('%s connection closed before receiving the password', reader.peer.address)  # noqa
            self.connections_table.insert(reader.peer, 'connection closed before receiving the password')  # noqa
            return False

        if self.users_table.is_password_valid(username, password):
            logger.debug('%s sent the correct login password', reader.peer.address)  # noqa
            # writer.peer.is_admin points to the same location in memory so its value also gets updated
            reader.peer.is_admin = self.users_table.is_admin(username)  # noqa
            return True

        logger.info('%s sent the wrong login password, closing connection', reader.peer.address)  # noqa
        self.connections_table.insert(reader.peer, 'rejected: wrong login password')  # noqa
        await self._write_error(ValueError('Wrong login password'), requester=self._network_name, writer=writer)
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
        logger.info('%s requesting password from %s', self, writer.peer.address)  # noqa
        await self.write_request(writer, 'password', self._network_name)
        password = await self.get_handshake_data(reader)
        if not password:  # then the connection closed prematurely
            logger.info('%s connection closed before receiving the password', reader.peer.address)  # noqa
            self.connections_table.insert(reader.peer, 'connection closed before receiving the password')  # noqa
            return False

        if password == self.password:
            logger.debug('%s sent the correct password', reader.peer.address)  # noqa
            return True

        logger.info('%s sent the wrong Manager password, closing connection', reader.peer.address)  # noqa
        self.connections_table.insert(reader.peer, 'rejected: wrong Manager password')  # noqa
        await self._write_error(ValueError('Wrong Manager password'),
                                requester=self._network_name, writer=writer)
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
        logger.info('%s requesting identity from %s', self, writer.peer.address)  # noqa
        await self.write_request(writer, 'identity')
        identity = await self.get_handshake_data(reader)

        if identity is None:  # then the connection closed prematurely (a certificate request?)
            return None
        elif isinstance(identity, str):
            identity = parse_terminal_input(identity)

        logger.debug('%s has identity %s', reader.peer.address, identity)  # noqa

        try:
            # writer.peer.network_name points to the same location in memory so its value also gets updated
            reader.peer.network_name = f'{identity["name"]}[{reader.peer.address}]'  # noqa

            typ = identity['type'].lower()
            if typ == 'client':
                self.clients[reader.peer.network_name] = {  # noqa
                    'name': identity['name'],
                    'address': reader.peer.address,  # noqa
                    'language': identity.get('language', 'unknown'),
                    'os': identity.get('os', 'unknown'),
                }
                self.client_writers[reader.peer.network_name] = writer  # noqa
                logger.info('%s is a new Client connection', reader.peer.network_name)  # noqa
            elif typ == 'service':
                if identity['name'] in self.services:
                    raise NameError(f'A {identity["name"]!r} service is already running on the Manager')
                self.services[identity['name']] = {
                    'attributes': identity['attributes'],
                    'address': reader.peer.address,  # noqa
                    'language': identity.get('language', 'unknown'),
                    'os': identity.get('os', 'unknown'),
                    'max_clients': identity.get('max_clients', -1),
                }
                self.service_writers[identity['name']] = writer
                self.service_links[identity['name']] = set()
                logger.info('%s is a new Service connection', reader.peer.network_name)  # noqa
            else:
                raise TypeError(f'Unknown connection type {typ!r}. Must be "client" or "service"')

            self.connections_table.insert(reader.peer, f'connected as a {typ}')  # noqa
            return typ

        except (TypeError, KeyError, NameError) as e:
            logger.info('%s sent an invalid identity, closing connection', reader.peer.address)  # noqa
            self.connections_table.insert(reader.peer, 'rejected: invalid identity')  # noqa
            await self._write_error(e, requester=self._network_name, writer=writer)
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
            data = (await reader.readline()).decode().rstrip()
        except (ConnectionError, UnicodeDecodeError):
            # then most likely the connection was for a certificate request, or,
            # the connection is trying to use a certificate and the Manage has TLS disabled
            logger.info('%s connection closed prematurely', reader.peer.address)  # noqa
            self.connections_table.insert(reader.peer, 'connection closed prematurely')  # noqa
            return None

        try:
            # ideally the response from the connected device will be in
            # the required JSON format
            return deserialize(data)['result']
        except:  # noqa
            # however, if connecting via a terminal, e.g. openssl s_client, then it is convenient
            # to not manually type the JSON format and let the Manager parse the raw input
            return data

    async def handler(self, reader, writer):
        """Handles requests from the connected :class:`~msl.network.client.Client`\\s and
        replies or notifications from the connected :class:`~msl.network.service.Service`\\s.

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.
        """
        reader_name = reader.peer.network_name  # noqa
        writer_name = writer.peer.network_name  # noqa
        while True:
            try:
                line = await reader.readline()
            except ConnectionResetError:
                return  # then the device disconnected abruptly

            if not line:
                return

            if len(line) > self._max_debug_length:
                half = self._max_debug_length//2
                logger.debug('%s: %s ... %s', reader_name, line[:half], line[-half:])
            else:
                logger.debug('%s: %s', reader_name, line)

            try:
                data = deserialize(line)
            except Exception as e:
                data = parse_terminal_input(line.decode())
                if not data:
                    await self._write_error(e, requester=reader_name, writer=writer)
                    continue

            if 'result' in data:
                # then data is a reply or notification from a Service so send it to the Client(s)
                if data['uid'] == NOTIFICATION_UID:
                    # emit the notification from the Service to all linked Clients
                    logger.info('%r emitted a notification', data['service'])
                    for client_address in self.service_links[data['service']]:
                        try:
                            self.client_writers[client_address].write(line)
                            await self.client_writers[client_address].drain()
                        except:  # noqa
                            logger.info('%s is no longer available to send the notification to',
                                        client_address)
                elif data['requester'] is None:
                    logger.info('%s is not able to deserialize the bytes', reader_name)
                else:
                    try:
                        self.client_writers[data['requester']].write(line)
                        await self.client_writers[data['requester']].drain()
                    except:  # noqa
                        logger.info('%s is no longer available to send the reply to', data['requester'])
            elif data['service'] == 'Manager':
                # then the Client is requesting something from the Manager
                if data['attribute'] == 'identity':
                    await self._write_result(self.identity(), requester=reader_name, uid=data['uid'], writer=writer)
                elif data['attribute'] == 'link':
                    try:
                        await self.link(writer, data.get('uid', ''), data['args'][0])
                    except Exception as e:
                        logger.error('%s: %s', e.__class__.__name__, e)
                        await self._write_error(e, requester=reader_name, uid=data.get('uid', ''), writer=writer)
                elif data['attribute'] == 'unlink':
                    try:
                        await self.unlink(writer, data.get('uid', ''), data['args'][0])
                    except Exception as e:
                        logger.error('%s: %s', e.__class__.__name__, e)
                        await self._write_error(e, requester=reader_name, uid=data.get('uid', ''), writer=writer)
                else:
                    # the peer needs administrative rights to send any other request to the Manager
                    logger.info('received an admin request %r from %s', data['attribute'], reader_name)
                    if not reader.peer.is_admin:  # noqa
                        await self.check_user(reader, writer)
                        if not reader.peer.is_admin:  # noqa
                            await self._write_error(
                                ValueError('You must be an administrator to send this request to the Manager'),
                                requester=reader_name,
                                writer=writer
                            )
                            continue
                    # the peer is an administrator, so execute the request
                    if data['attribute'] == SHUTDOWN_MANAGER:
                        self._loop.stop()
                        return
                    try:
                        # check for multiple dots "." in the name of the attribute
                        attrib = self
                        for item in data['attribute'].split('.'):
                            attrib = getattr(attrib, item)
                    except AttributeError as e:
                        logger.error('AttributeError: %s', e)
                        await self._write_error(e, requester=reader_name, writer=writer)
                        continue
                    try:
                        # send the reply back to the Client
                        if callable(attrib):
                            reply = attrib(*data['args'], **data['kwargs'])  # noqa
                        else:
                            reply = attrib
                        # do not include the uid in the reply
                        await self._write_result(reply, requester=reader_name, writer=writer)
                    except Exception as e:
                        logger.error('%s: %s', e.__class__.__name__, e)
                        await self._write_error(e, requester=reader_name, writer=writer)
            elif data['attribute'] == DISCONNECT_REQUEST:
                # then the device requested to disconnect
                return
            else:
                # send the request to the appropriate Service
                try:
                    data['requester'] = writer_name
                    await self._write(data, writer=self.service_writers[data['service']])
                    logger.info('%s requested %r from %r',
                                writer_name, data['attribute'], data['service'])
                except KeyError:
                    msg = f'the {data["service"]!r} Service is not connected to {self}'
                    logger.info('%s KeyError: %s', self, msg)
                    await self._write_error(KeyError(msg), requester=reader_name, writer=writer)

    async def remove_peer(self, id_type, writer):
        """Remove this peer from the registry of connected peers.

        Parameters
        ----------
        id_type : :class:`str`
            The type of the connection, either ``'client'`` or ``'service'``.
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the peer.
        """
        name = writer.peer.network_name  # noqa
        if id_type == 'client':
            try:
                del self.clients[name]
                del self.client_writers[name]
                logger.info('%s has been removed from the registry', name)
            except KeyError:  # ideally this exception should never occur
                logger.error('%s is not in the Client dictionary', name)

            # remove this Client from all Services that it was linked with
            for service_name, client_addresses in self.service_links.items():
                if name in client_addresses:
                    try:
                        await self.unlink(writer, '', service_name)
                    except:  # noqa
                        pass
        else:
            for service in self.services:
                if self.services[service]['address'] == writer.peer.address:  # noqa
                    try:
                        del self.service_links[service]
                        del self.services[service]
                        del self.service_writers[service]
                        logger.info('%s service has been removed from the registry', name)
                    except KeyError:  # ideally this exception should never occur
                        logger.error('%s is not in the Service dictionary', name)
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
        logger.info('%s connection closed', writer.peer.network_name)  # noqa
        self.connections_table.insert(writer.peer, 'disconnected')  # noqa

    async def shutdown_manager(self):
        """
        Disconnect all :class:`~msl.network.service.Service`\\s and
        :class:`~msl.network.client.Client`\\s from the :class:`Manager`
        and then shut down the :class:`Manager`.
        """
        # convert the dict_values to a list since we are modifying the dictionary in remove_peer()
        for writer in list(self.client_writers.values()):
            await self.close_writer(writer)
            await self.remove_peer('client', writer)
        for writer in list(self.service_writers.values()):
            await self.close_writer(writer)
            await self.remove_peer('service', writer)

    def identity(self):
        """:class:`dict`: The :obj:`~msl.network.network.Network.identity` of
        the Network :class:`Manager`."""
        return self._identity

    async def link(self, writer, uid, service):
        """A request from a :class:`~msl.network.client.Client` to link it
        with a :class:`~msl.network.service.Service`.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the :class:`~msl.network.client.Client`.
        uid : :class:`str`
            The unique identifier of the request.
        service : :class:`str`
            The name of the :class:`~msl.network.service.Service` that the
            :class:`~msl.network.client.Client` wants to link with.
        """
        writer_name = writer.peer.network_name  # noqa
        try:
            identity = self.services[service]
        except KeyError:
            msg = f'the {service!r} service does not exist, cannot link with {writer_name}'
            logger.info(msg)
            await self._write_error(KeyError(msg), requester=writer_name, uid=uid, writer=writer)
        else:
            if writer_name in self.service_links[service]:
                # a Client wants to re-link with the same Service
                logger.info('re-linked %s with %r', writer_name, service)
                await self._write_result(identity, requester=writer_name, uid=uid, writer=writer)
            elif identity['max_clients'] <= 0 or len(self.service_links[service]) < identity['max_clients']:
                self.service_links[service].add(writer_name)
                logger.info('linked %s with %r', writer_name, service)
                await self._write_result(identity, requester=writer_name, uid=uid, writer=writer)
            else:
                join = '\n  '.join(self.service_links[service])
                msg = f'The maximum number of Clients are already linked with {service!r}\n' \
                      f'The linked Clients are:\n  {join}'
                logger.info(msg)
                await self._write_error(PermissionError(msg), requester=writer_name, uid=uid, writer=writer)

    async def unlink(self, writer, uid, service):
        """A request from a :class:`~msl.network.client.Client` to unlink it
        from a :class:`~msl.network.service.Service`.

        .. versionadded:: 0.5

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the :class:`~msl.network.client.Client`.
        uid : :class:`str`
            The unique identifier of the request.
        service : :class:`str`
            The name of the :class:`~msl.network.service.Service` that the
            :class:`~msl.network.client.Client` wants to unlink from.
        """
        writer_name = writer.peer.network_name  # noqa
        try:
            network_names = self.service_links[service]
        except KeyError:
            msg = f'{service!r} service does not exist, cannot unlink {writer_name} from it'
            logger.info(msg)
            await self._write_error(KeyError(msg), requester=writer_name, uid=uid, writer=writer)
        else:
            try:
                network_names.remove(writer_name)
            except KeyError:
                msg = f'cannot unlink {writer_name}, it was not linked with {service!r}'
                logger.info(msg)
                await self._write_error(KeyError(msg), requester=writer_name, uid=uid, writer=writer)
            else:
                logger.info('unlinked %s from %r', writer_name, service)
                await self._write_result(True, requester=writer_name, uid=uid, writer=writer)

    async def write_request(self, writer, attribute, *args, **kwargs):
        """Write a request to a :class:`~msl.network.client.Client` or to a
        :class:`~msl.network.service.Service`.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer of the :class:`~msl.network.client.Client` or
            :class:`~msl.network.service.Service`.
        attribute : :class:`str`
            The name of the attribute to request.
        args
            The arguments that `attribute` requires.
        kwargs
            The key-value pairs that `attribute` requires.
        """
        await self._write(
            {
                'args': args,
                'attribute': attribute,
                'error': False,
                'kwargs': kwargs,
                'requester': self._network_name,
                'uid': '',
            },
            writer=writer
        )


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

        if self.hostname in LOCALHOST_ALIASES:
            self.address = f'{HOSTNAME}:{self.port}'
        else:
            self.address = f'{self.hostname}:{self.port}'

        # this value will be updated when the identity is requested
        self.network_name = f'<Unknown>[{self.address}]'


def run_forever(
        *, host=None, port=PORT, auth_hostname=False, auth_login=False,
        auth_password=None, database=None, disable_tls=False, cert_file=None,
        key_file=None, key_file_password=None, log_level='INFO', log_file=None):
    """Start the event loop for the Network :class:`.Manager`.

    This is a blocking function. It will not return until the event loop of
    the :class:`.Manager` has stopped.

    .. versionadded:: 0.4

    .. versionchanged:: 1.0
       Renamed `certfile` to `cert_file`.
       Renamed `keyfile` to `key_file`.
       Renamed `keyfile_password` to `key_file_password`.
       Renamed `logfile` to `log_file`.
       Removed the `debug` keyword argument.
       Added the `log_level` keyword argument.
       Added the `host` keyword argument.

    Parameters
    ----------
    host : :class:`str`, optional
        The hostname or IP address to run the Network :class:`Manager` on.
        If unspecified then all network interfaces are used.
    port : :class:`int`, optional
        The port number to run the Network :class:`Manager` on.
    auth_hostname : :class:`bool`, optional
        If :data:`True` then only connections from trusted hosts are allowed.
        If enabling `auth_hostname` then do not specify an `auth_password`
        and do not enable `auth_login`. Run ``msl-network hostname --help``
        for more details.
    auth_login : :class:`bool`, optional
        If :data:`True` then checks a users login credentials (the username
        and password) before a :class:`~msl.network.client.Client` or
        :class:`~msl.network.service.Service` successfully connects. If enabling
        `auth_login` then do not specify an `auth_password` and do not enable
        `auth_hostname`. Run ``msl-network user --help`` for more details.
    auth_password : :class:`str`, optional
        The password of the Network :class:`Manager`. Essentially, this can be a
        thought of as a single password that all :class:`~msl.network.client.Client`\\s
        and :class:`~msl.network.service.Service`\\s need to specify before the
        connection to the Network :class:`Manager` is successful. Can be a path
        to a file that contains the password on the first line in the file
        (**WARNING!!** if the path does not exist then the value of the path
        becomes the password). If using an `auth_password` then do not enable
        `auth_login` nor `auth_hostname`.
    database : :class:`str`, optional
        The path to the sqlite3 database that contains the records for the
        following tables -- :class:`.ConnectionsTable`, :class:`.HostnamesTable`,
        :class:`.UsersTable`. If :data:`None` then loads the default database.
    disable_tls : :class:`bool`, optional
        Whether to use TLS for the communication protocol.
    cert_file : :class:`str`, optional
        The path to the TLS certificate file. See
        :meth:`~ssl.SSLContext.load_cert_chain`
        for more details. Only required if using TLS.
    key_file : :class:`str`, optional
        The path to the TLS key file. See
        :meth:`~ssl.SSLContext.load_cert_chain` for more details.
    key_file_password : :class:`str`, optional
        The password to decrypt the `key_file`. See :meth:`~ssl.SSLContext.load_cert_chain`
        for more details. Can be a path to a file that contains the password on
        the first line in the file (**WARNING!!** if the path does not exist
        then the value of the path becomes the password).
    log_level : :class:`str` or :class:`int`, optional
        The :ref:`logging level <levels>` to initially use. Can also be changed
        via an :meth:`~msl.network.client.Client.admin_request`.
    log_file : :class:`str`, optional
        The file path to write logging messages to. If :data:`None` then uses
        the default file path.
    """
    output = _create_manager_and_loop(
        host=host, port=port, auth_hostname=auth_hostname, auth_login=auth_login,
        auth_password=auth_password, database=database,
        disable_tls=disable_tls, cert_file=cert_file, key_file=key_file,
        key_file_password=key_file_password, log_level=log_level, log_file=log_file
    )

    if not output:
        return

    try:
        output['loop'].run_forever()
    except KeyboardInterrupt:
        logger.info('CTRL+C keyboard interrupt received')
    finally:
        _cleanup(**output)


def run_services(*services, **kwargs):
    """This function starts the Network :class:`.Manager` and then starts the
    specified :class:`~msl.network.service.Service`\\s.

    This is a convenience function for running the Network :class:`.Manager`
    only when the specified :class:`~msl.network.service.Service`\\s are all
    connected to the :class:`.Manager`. Once all :class:`~msl.network.service.Service`\\s
    disconnect from the :class:`.Manager` then the :class:`.Manager` shuts down.

    This is a blocking call. It will not return until the event loop of
    the :class:`.Manager` has stopped.

    .. versionadded:: 0.4

    Parameters
    ----------
    services
        The :class:`~msl.network.service.Service`\\s to run on the
        :class:`.Manager`. Each :class:`~msl.network.service.Service` must be
        instantiated but not started. This :func:`run_services` function will
        start each :class:`~msl.network.service.Service`.
    kwargs
        Keyword arguments are passed to :func:`run_forever` and to
        :meth:`~msl.network.service.Service.start`. The keyword arguments that
        are passed to :func:`run_forever` and :meth:`~msl.network.service.Service.start`
        that are not valid for that function are silently ignored.

    Examples
    --------

    If you want to allow a :class:`~msl.network.client.Client` to be able to shut down a
    :class:`~msl.network.service.Service` then implement a public ``shutdown_service()``
    method on the :class:`~msl.network.service.Service`. For example, the following
    ``shutdownable_example.py`` is a script that starts a Network :class:`.Manager`
    and two :class:`~msl.network.service.Service`\\s

    .. code-block:: python

        # shutdownable_example.py

        from msl.network import Service, run_services

        class AddService(Service):

            def add(self, a, b):
                return a + b

            def shutdown_service(self, *args, **kwargs):
                # do whatever you need to do before the AddService shuts down
                # return whatever you want
                return True

        class SubtractService(Service):

            def subtract(self, a, b):
                return a - b

            def shutdown_service(self, *args, **kwargs):
                # do whatever you need to do before the SubtractService shuts down
                # return whatever you want
                return 'Success!'

        run_services(AddService(), SubtractService())

    Then the :class:`~msl.network.client.Client` script could be

    .. code-block:: python

        from msl.network import connect

        cxn = connect()
        a = cxn.link('AddService')
        s = cxn.link('SubtractService')
        assert a.add(1, 2) == 3
        assert s.subtract(1, 2) == -1
        a.shutdown_service()
        s.shutdown_service()

    When both :class:`~msl.network.service.Service`\\s have shut down then the Network
    :class:`.Manager` will also shut down and the :func:`run_services` function
    will no longer be blocking the execution of ``shutdownable_example.py``.
    """
    if not services:
        msg = 'Warning... no services have been specified'
        logger.error(msg)
        print(msg, file=sys.stderr)
        return

    for service in services:
        if not isinstance(service, Service):
            raise TypeError(f'All services must be of type {Service}')

    manager_kwargs = filter_run_forever_kwargs(**kwargs)
    service_kwargs = filter_service_start_kwargs(**kwargs)

    output = _create_manager_and_loop(**manager_kwargs)
    if not output:
        return

    async def start_service(s):
        await output['loop'].run_in_executor(None, lambda: s.start(**service_kwargs))

    async def gather():
        await asyncio.gather(*tasks)

    tasks = [start_service(service) for service in services]

    try:
        output['loop'].run_until_complete(gather())
    except KeyboardInterrupt:
        logger.info('CTRL+C keyboard interrupt received')
    finally:
        _cleanup(**output)


def filter_run_forever_kwargs(**kwargs):
    """From the specified keyword arguments only return those that are valid for
    :func:`~msl.network.manager.run_forever`.

    .. versionadded:: 0.4

    Parameters
    ----------
    kwargs
        All keyword arguments that are not part of the function signature for
        :func:`~msl.network.manager.run_forever` are silently ignored and are
        not included in the output.

    Returns
    -------
    :class:`dict`
        Valid keyword arguments that can be passed to
        :func:`~msl.network.manager.run_forever`.
    """
    kws = {}
    for item in inspect.getfullargspec(run_forever).kwonlyargs:
        if item in kwargs:
            kws[item] = kwargs[item]

    # the manager uses an `auth_password` kwarg but a service uses a
    # `password_manager` kwarg however, these kwargs represent the same thing
    if 'password_manager' in kwargs and 'auth_password' not in kws:
        kws['auth_password'] = kwargs['password_manager']

    return kws


def _create_manager_and_loop(
        *, host=None, port=PORT, auth_hostname=False, auth_login=False,
        auth_password=None, database=None, disable_tls=False, cert_file=None,
        key_file=None, key_file_password=None, log_level='INFO', log_file=None):

    # set up logging -- FileHandler and StreamHandler
    if log_file is None:
        now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        log_file = os.path.join(HOME_DIR, 'logs', f'manager-{now}.log')
    ensure_root_path(log_file)

    # set the root logger level to DEBUG and make sure that it has no handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    logging.getLogger('asyncio').setLevel(logging.WARNING)

    # add a FileHandler
    fh = logging.FileHandler(log_file, mode='wt')
    fh.setLevel(logging.DEBUG)
    ff = logging.Formatter('%(asctime)s [%(levelname)-8s] %(name)s - %(message)s')
    ff.default_msec_format = '%s.%03d'
    fh.setFormatter(ff)
    root_logger.addHandler(fh)

    # add a StreamHandler and its log level can be decided from the command line
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.DEBUG)
    sf = logging.Formatter('%(asctime)s [%(levelname)-5s] %(name)s - %(message)s')
    sf.default_msec_format = '%s.%03d'
    sh.setFormatter(sf)
    root_logger.addHandler(sh)

    if not Manager.set_logging_level(log_level):
        msg = f'ValueError: Cannot set logging level to {log_level!r}'
        logger.error(msg)
        print(msg, file=sys.stderr)
        return

    # get the port number
    try:
        port = int(port)
        if port <= 0:
            raise ValueError
    except ValueError:
        msg = 'ValueError: The port must be a positive integer'
        logger.error(msg)
        print(msg, file=sys.stderr)
        return

    # create the SSL context
    context = None
    if not disable_tls:
        # get the password to decrypt the private key
        if isinstance(key_file_password, (list, tuple)):
            key_file_password = ' '.join(key_file_password)
        if key_file_password is not None and os.path.isfile(key_file_password):
            with open(key_file_password, 'r') as fp:
                key_file_password = fp.readline().strip()

        # get the path to the certificate and to the private key
        if cert_file is None and key_file is None:
            if host is None:
                key_file = cryptography.get_default_key_path()
                cert_file = cryptography.get_default_cert_path()
            else:
                key_file = os.path.join(KEY_DIR, f'{host}.key')
                cert_file = os.path.join(CERT_DIR, f'{host}.crt')

            if not os.path.isfile(key_file):
                cryptography.generate_key(path=key_file, password=key_file_password)

            if not os.path.isfile(cert_file):
                cryptography.generate_certificate(
                    path=cert_file, key_path=key_file, key_password=key_file_password
                )

        elif cert_file is None and key_file is not None:
            # create (or overwrite) the default certificate to match the key
            cert_file = cryptography.generate_certificate(
                key_path=key_file, key_password=key_file_password)

        elif cert_file is not None and key_file is None:
            pass  # assume that the certificate file also contains the private key

        context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)  # noqa
        context.load_cert_chain(cert_file, keyfile=key_file, password=key_file_password)
        logger.info('loaded certificate %s', cert_file)

    # get database file
    if database is not None:
        if not os.path.isfile(database):
            ensure_root_path(database)
    else:
        database = DATABASE

    # load the connections table
    conn_table = ConnectionsTable(database=database)
    logger.info('loaded the %r table from %s', conn_table.NAME, conn_table.path)

    # load the auth_hostnames table
    hostnames_table = HostnamesTable(database=database)
    logger.info('loaded the %r table from %s', hostnames_table.NAME, hostnames_table.path)

    # load the auth_users table for the login credentials
    users_table = UsersTable(database=database)
    logger.info('loaded the %r table from %s', users_table.NAME, users_table.path)

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
            name = users_table.NAME
            msg = f'The {name!r} table is empty, no one could log in\n' \
                  f'To add a user to the {name!r} table run the ' \
                  f'"msl-network user" command'
            logger.error(msg)
            print(msg, file=sys.stderr)
            return
    else:
        users_table.close()
        conn_table.close()
        hostnames_table.close()
        msg = 'Cannot specify multiple authentication methods'
        logger.error(msg)
        print(msg, file=sys.stderr)
        return

    if hostnames:
        logger.info('using trusted hosts for authentication')
    elif password:
        logger.info('using a password for authentication')
    elif login:
        logger.info('using a login for authentication')
    else:
        logger.info('not using authentication')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # create the network manager
    manager = Manager(port, password, login, hostnames, conn_table,
                      users_table, hostnames_table, loop)

    try:
        server = loop.run_until_complete(
            asyncio.start_server(manager.new_connection, host=host, port=port,
                                 ssl=context, limit=sys.maxsize)
        )
    except OSError as err:
        users_table.close()
        conn_table.close()
        hostnames_table.close()
        logger.error(err)
        print(err, file=sys.stderr)
        return

    state = 'ENABLED' if context else 'DISABLED'
    logger.info('%s %s:%d (TLS %s)',
                NETWORK_MANAGER_RUNNING_PREFIX,
                host or HOSTNAME,
                port,
                state)

    return {
        'manager': manager,
        'loop': loop,
        'server': server,
        'db_tables': [conn_table, hostnames_table, users_table]
    }


def _cleanup(manager, loop, server, db_tables):
    logger.info('shutting down the Network Manager')

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

    logger.info('closing the connection server')
    server.close()
    loop.run_until_complete(server.wait_closed())
    logger.info('closing the event loop')
    try:
        loop.close()
    except RuntimeError:
        pass

    # close the database tables
    for table in db_tables:
        table.close()
