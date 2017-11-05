"""
An asynchronous Network Manager.
"""
import ssl
import json
import asyncio
import logging
import platform

from .network import Network
from .utils import parse_terminal_input
from .constants import HOSTNAME
from .database import ConnectionsDatabase

log = logging.getLogger(__name__)


class Manager(Network):

    def __init__(self, port, authentication, database, debug):
        """An asynchronous Network Manager.

        .. attention::
            Not to be instantiated directly. To be called from the command line.
        """
        self._debug = debug
        self._network_id = f'{HOSTNAME}:{port}'
        self.database = database
        self.authentication = authentication
        self.clients = dict()
        self.services = dict()
        self.service_writers = dict()
        self.client_writers = dict()
        self.client_service_link = dict()

        self._identity = {
            'hostname': HOSTNAME,
            'port': port,
            'language': 'Python ' + platform.python_version(),
            'os': '{} {} {}'.format(platform.system(), platform.release(), platform.machine()),
            'clients': self.clients,
            'services': self.services,
            'attributes': {
                'identity': '() -> dict',
                'link': '(service:str) -> bool',
            }
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
        peer = writer.get_extra_info('peername')
        address = '{}:{}'.format(peer[0], peer[1])
        log.info(f'new connection request from {address}')

        # create a new attribute called 'name' for the StreamReader and StreamWriter
        # this is helpful when debugging
        reader.name = address
        writer.name = address

        # check the authentication (either a list of trusted hostname's or a password)
        if self.authentication is not None:
            log.info(f'{self._network_id} checking authentication from {address}')
            if isinstance(self.authentication, list):
                if peer[0] not in self.authentication:
                    log.info(peer[0] + ' is not a trusted hostname, closing connection')
                    self.database.insert(peer, 'rejected: untrusted hostname')
                    self.send_error(writer, ValueError(peer[0] + ' is not a trusted hostname.'))
                    await self.close_writer(writer, address)
                    return
                log.debug(peer[0] + ' is a trusted hostname')
            else:
                if not await self.check_password(address, reader, writer):
                    return

        # check that the identity of the connecting device is valid
        identity = await self.check_identity(address, reader, writer)
        if not identity:
            return

        # the device is now connected, handle requests until it requests to disconnect
        self.database.insert(peer, 'connected')
        await self.handle_requests(identity, address, reader, writer)

        # disconnect the device
        await self.close_writer(writer, address)
        self.remove_peer(identity, address, writer.name)

    async def check_password(self, address, reader, writer):
        """Check the password from the connected device.

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
            return False

        if password == self.authentication:
            log.debug(f'{address} sent the correct password')
            return True

        log.info(f'{address} sent the wrong password, closing connection')
        self.database.insert(address.split(':'), 'rejected: wrong password')
        self.send_error(writer, ValueError('Wrong password, {!r}'.format(password)))
        await self.close_writer(writer, address)
        return False

    async def check_identity(self, address, reader, writer):
        """Check the :obj:`~msl.network.network.Network.identity` from the connected device.

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
        log.info(f'{self._network_id} requesting identity from {address}')
        self.send_request(writer, attribute='identity')
        identity = await self.get_handshake_data(address, reader)

        if identity is None:  # then the connection closed prematurely (a certificate request?)
            return ''
        elif isinstance(identity, str):
            identity = parse_terminal_input(identity)

        log.debug(f'{address} sent {identity}')

        try:
            name = f'{identity["name"]}[{address}]'
            reader.name = name
            writer.name = name

            type_ = identity['type'].lower()
            if type_ == 'client':
                self.clients[address] = identity['name']
                self.client_writers[address] = writer
                log.info(f'{name} is a new Client connection')
            elif type_ == 'service':
                if identity['name'] in self.services:
                    raise NameError(f'A {identity["name"]} service is already running on the Manager')
                self.services[identity['name']] = {
                    'attributes': identity['attributes'],
                    'address': identity.get('address', address),
                    'language': identity.get('language', 'Unknown'),
                    'os': identity.get('os', 'Unknown'),
                }
                self.service_writers[identity['name']] = (writer, address)
                log.info(f'{name} is a new Service connection')
            else:
                raise TypeError(f'Unknown connection type "{type_}". Must be "client" or "service"')

            return type_

        except (TypeError, KeyError) as e:
            log.info(address + ' sent an invalid identity, closing connection')
            self.database.insert(address.split(':'), 'rejected: invalid identity')
            self.send_error(writer, e)
            await self.close_writer(writer, address)
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
            # ideally the response from the connected device will be in
            # the required JSON format
            return json.loads(data)['return']
        except (json.JSONDecodeError, KeyError):
            # it is convenient to return the string if the connection
            # is through a terminal, e.g. Putty
            return data

    async def handle_requests(self, identity, address, reader, writer):
        """Handle requests from the connected :class:`~msl.network.client.Client`.

        A :class:`~msl.network.client.Client` that is sending requests to the Network
        :class:`Manager` **MUST** send a JSON_ object with the following format::

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
        """
        while True:

            try:
                line = await reader.readline()
            except ConnectionResetError as e:
                return  # then the device disconnected abruptly

            if self._debug:
                log.debug(f'{reader.name} sent {line}')

            if not line:
                return

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                data = parse_terminal_input(line.decode(self.encoding))
                if not data:
                    self.send_error(writer, e)
                    continue

            if 'return' in data:  # then data is a reply from a Service so send it to the Client
                sent = False
                for client_address, service_address in self.client_service_link.items():
                    if address == service_address:
                        self.send_line(self.client_writers[client_address], line)
                        sent = True
                        break
                if not sent:
                    log.error(f'Cannot find the Client to send the reply from {reader.name}')
            elif data['service'] is None:  # then the Client is requesting something from the Manager
                if data['attribute'] == 'identity':
                    self.send_reply(writer, self.identity())
                elif data['attribute'] == 'link':
                    try:
                        success, msg = self.link(address, writer.name, **data['parameters'])
                    except Exception as e:
                        log.error(f'{e.__class__.__name__}: {e}')
                        self.send_error(writer, e)
                        continue
                    if success:
                        self.send_reply(writer, success)
                    else:
                        self.send_error(writer, ValueError(msg))
                else:
                    e = AttributeError(f'The Manager does not have a {data["attribute"]} attribute to call.')
                    self.send_error(writer, e)
            elif data['attribute'] == '__disconnect__':
                return  # then the device requested to disconnect
            else:  # send the request to the appropriate Service
                try:
                    service, _ = self.service_writers[data['service']]
                except KeyError as e:
                    self.send_error(writer, e)
                else:
                    self.send_data(service, data)

    def remove_peer(self, identity, address, name):
        """Remove this peer from the registry of connected peers.

        Parameters
        ----------
        identity : :obj:`str`
            The type of the connection, either ``'client'`` or ``'service'``.
        address : :obj:`str`
            The address, ``'host:port'`` of the connected device.
        name : :obj:`str`
            The name of the connected device.
        """
        if identity == 'client':
            try:
                del self.clients[address]
                log.info(f'{name} has been removed from the registry')
            except KeyError:  # ideally this exception should never occur
                pass
        else:
            for service in self.services:
                if self.services[service]['address'] == address:
                    del self.services[service]
                    log.info(f'{name} service has been removed from the registry')
                    # TODO notify the Client that the Service is disconnected
                    break

    async def close_writer(self, writer, address):
        """Close the connection to the :class:`asyncio.StreamWriter`.

        Log's that the connection is closing, drains the writer and then
        closes it.

        Parameters
        ----------
        writer : :class:`asyncio.StreamWriter`
            The stream writer.
        address : :obj:`str`
            The address, ``'host:port'`` of the connected device.
        """
        try:
            log.info(f'{writer.name} closing connection')
            await writer.drain()
            writer.close()
            log.info(f'{writer.name} connection closed')
            self.database.insert(address.split(':'), 'disconnected')
        except ConnectionResetError as e:
            log.error(f'{writer.name} failed to close -- {e}')

    async def shutdown_server(self):
        """Safely disconnect all :class:`~msl.network.service.Service`\'s and
        :class:`~msl.network.client.Client`\'s."""
        for address in self.client_writers:
            await self.close_writer(self.client_writers[address], address)
        for name in self.service_writers:
            await self.close_writer(*self.service_writers[name])

    def identity(self):
        """:obj:`dict`: The :obj:`~msl.network.network.Network.identity` about
        the Network :class:`Manager`."""
        return self._identity

    def link(self, client, name, service):
        """A request from the :class:`~msl.network.client.Client` to link it
        with a :class:`~msl.network.service.Service`.

        Parameters
        ----------
        client : :obj:`str`
            The address, ``'host:port'``, of the :class:`~msl.network.client.Client`.
        name : :obj:`str`
            The name of the :class:`~msl.network.client.Client`.
        service : :obj:`str`
            The name of the :class:`~msl.network.service.Service` that the
            :class:`~msl.network.client.Client` wants to link with.

        Returns
        -------
        :obj:`bool`
            Whether the link was successful. The only reason why the link
            would not be successful is if a :class:`~msl.network.service.Service`
            named `service` is currently not connected to the Manager.
        :obj:`str`
            A message describing the outcome of the link request.
        """
        try:
            service_address = self.services[service]['address']
            # must use the client_address as the key since the address of a
            # Client is unique, whereas a Service can have multiple Clients
            # connected to it
            self.client_service_link[client] = service_address
            msg = f'linked {name} with {service}'
            log.info(msg)
            return True, msg
        except KeyError as e:
            msg = f'{service} service does not exist, could not link with {name}'
            log.error(msg)
            return False, msg


def start(auth, port, cert, key, key_password, database, debug):
    """Start the asynchronous network manager event loop.

    .. attention::
        Not to be called directly. To be called from the command line.
    """

    # create the SSL context
    context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=cert, keyfile=key, password=key_password)

    log.info(f'loaded certificate {cert}')

    # load the connections database
    db = ConnectionsDatabase(database)
    log.info(f'loaded database {db.path}')

    if isinstance(auth, list):
        log.debug('using trusted hosts for authentication')
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

    # loop.set_debug(debug)

    server = loop.run_until_complete(
        asyncio.start_server(manager.new_connection, port=port, ssl=context, loop=loop)
    )

    log.info(f'Network Manager running on {HOSTNAME}:{port} using {context.protocol.name}')

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info('CTRL+C keyboard interrupt received')
    finally:
        log.info('shutting down the network manager')

        if manager.client_writers or manager.service_writers:
            loop.run_until_complete(manager.shutdown_server())

        for task in asyncio.Task.all_tasks():
            log.info(f'cancelling {task}')
            task.cancel()

        log.info('closing server')
        server.close()
        loop.run_until_complete(server.wait_closed())
        log.info('closing event loop')
        loop.close()
