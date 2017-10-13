"""
Command line interface for the ``start`` command.
"""
import os
import ssl
import socket
import asyncio
import logging

from . import crypto, constants, manager


HELP = 'Start the asynchronous network manager.'

DESCRIPTION = HELP + """
"""

EPILOG = """
Examples:
    # start the network manager using the default settings
    msl-network start

    # start the network manager on port 8326
    msl-network start --port 8326
    
    # require a password for clients, servers and other network managers 
    # to be able to connect to this network manager
    msl-network start --password abc 123

    # use a specific certificate and key for the secure SSL/TLS protocol 
    msl-network start --cert path/to/cert.pem --key path/to/key.pem
    
See Also:
    msl-network keygen
    msl-network certgen
"""


def add_parser_start(parser):
    """Add a ``start`` command to the parser."""
    p = parser.add_parser(
        'start',
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    p.add_argument(
        '--port',
        default=constants.PORT,
        help='The port number to use for the network manager.\n'
             'Default is %(default)s.'
    )
    p.add_argument(
        '--password',
        nargs='+',
        help='The password (passphrase) that is required for a client,\n'
             'server or another network manager to be able to connect\n'
             'to this network manager. Default is None (no password).'
    )
    p.add_argument(
        '--cert',
        help='The path to a certificate file to use for the secure TLS\n'
             'connection. If omitted then a default certificate is loaded\n'
             '(or created) and used. See also: msl-network certgen'
    )
    p.add_argument(
        '--key',
        help='The path to the private key which was used to digitally\n'
             'sign the certificate. If omitted then load (or create) the\n'
             'default key. If --cert is omitted and --key is specified\n'
             'then this key is used to create (or overwrite) the default\n'
             'certificate and this new certificate will be used for the\n'
             'secure TLS connection. See also: msl-network keygen'
    )
    p.add_argument(
        '--key-password',
        nargs='+',
        help='The password (passphrase) to use to decrypt the private key.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``start`` command."""

    # set up logging
    log = logging.getLogger('main')
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get('MSL_NETWORK_DEBUG', False) else logging.INFO,
        format='%(asctime)s [%(levelname)s] -- %(name)s -- %(message)s',
    )

    # get the port number
    try:
        port = int(args.port)
    except ValueError:
        print('The --port value must be in integer')
        return

    # get the password that is required for clients, servers and other network managers to connect
    password = None if args.password is None else ' '.join(args.password)

    # get the password to decrypt the private key
    key_password = None if args.key_password is None else ' '.join(args.key_password)

    # get the certificate and the private key
    certfile, keyfile = args.cert, args.key
    if certfile is None and keyfile is None:
        keyfile = crypto.get_default_key_path()
        if not os.path.isfile(keyfile):
            crypto.generate_key(keyfile, password=key_password)
        certfile = crypto.get_default_cert_path()
        if not os.path.isfile(certfile):
            crypto.generate_certificate(certfile, key_path=keyfile, key_password=key_password)
    elif certfile is None and keyfile is not None:
        # create (or overwrite) the default certificate
        certfile = crypto.generate_certificate(None, key_path=keyfile, key_password=key_password)
    elif certfile is not None and keyfile is None:
        pass  # assume that the certificate file also contains the private key

    # create the SSL context
    context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile, password=key_password)

    # create the network manager
    mgr = manager.Manager(password)

    # create the event loop
    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(
        asyncio.start_server(mgr.new_connection, port=port, ssl=context, loop=loop)
    )

    log.info('network manager is running on {}:{} using {}'.format(socket.gethostname(), port, context.protocol.name))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info('CTRL+C keyboard interrupt received')
        pass

    log.info('shutting down the network manager...')
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
