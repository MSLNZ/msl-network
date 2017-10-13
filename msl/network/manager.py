"""
An asynchronous network manager.
"""
import json
import logging

log = logging.getLogger(__name__)


class Manager(object):

    def __init__(self, password):
        """An asynchronous network manager.

        Parameters
        ----------
        password : :obj:`str`
            The password (passphrase) that is required for a client, server or another
            network manager to be able to connect to this network manager.'
        """
        self.password = password

        self.clients = {}  # the clients that are connected
        self.servers = {}  # the servers that are connected
        self.managers = {}  # the other network managers that are connected

    async def new_connection(self, reader, writer):
        """Receive a new connection request.

        To accept the request the following steps must be performed successfully:

        1. Request the password (only if a password is required).
        2. Get the identity of the connecting object
            * Is it a client, sever or another network manager?
            * What function signatures does it accept?

        Parameters
        ----------
        reader : :class:`asyncio.StreamReader`
            The stream reader.
        writer : :class:`asyncio.StreamWriter`
            The stream writer.
        """
        log.info('new connection from {}'.format(writer.get_extra_info('peername')))

        if self.password is not None:
            if not await self.check_password(reader, writer):
                return

        identity = await self.get_identity(reader, writer)
        if identity is None:
            return

        await self.handle_requests(reader, writer)

        await writer.drain()
        log.info('connection from {} is closed'.format(writer.get_extra_info('peername')))

    async def check_password(self, reader, writer):
        peer_name = writer.get_extra_info('peername')
        log.info('requesting password from {}'.format(peer_name))
        writer.write(b'__password__')
        password = await reader.readline()
        if self.password == password.decode().strip():
            log.info('correct password received from {}'.format(peer_name))
            return True
        writer.write(b'Sorry, wrong password.')
        log.info('incorrect password received from {}, closing connection'.format(peer_name))
        writer.close()
        return False

    async def get_identity(self, reader, writer):
        peer_name = writer.get_extra_info('peername')
        log.info('requesting identity from {}'.format(peer_name))
        writer.write(b'__identity__')
        json_str = await reader.readline()
        try:
            data = json.loads(json_str.decode().strip())

            # the json data must have a 'name', 'connection_type' and 'functions' key
            name = data['name']
            connection_type = data['connection_type']
            functions = data['functions']

            # TODO add the reader and writer to the appropriate clients/servers/managers dict

            log.info('identification received from {}'.format(peer_name))
            return data
        except:
            writer.write(b'Sorry, invalid identification json string received.')
            log.error('invalid identification json string received from {}, closing connection'.format(peer_name))
            writer.close()
            return None

    async def handle_requests(self, reader, writer):
        peer_name = writer.get_extra_info('peername')
        while True:
            request = (await reader.readline()).decode().strip()
            if request == '__disconnect__':
                log.info('disconnection request from {}, closing connection'.format(peer_name))
                writer.close()
                return
