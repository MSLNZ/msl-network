"""
Command line interface for the ``start`` command.
"""
import os
import sys
import logging
from datetime import datetime

from . import crypto
from .manager import start_manager
from .utils import ensure_root_path
from .constants import HOME_DIR, PORT

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
        default=PORT,
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
        help='The password (passphrase) to use to decrypt the private key.\n'
             'Only required if the key file is encrypted.'
    )
    p.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Enable DEBUG logging messages.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``start`` command."""

    # set up logging
    now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    path = os.path.join(HOME_DIR, 'logs', 'manager-{}.log'.format(now))
    ensure_root_path(path)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s [%(levelname)-8s] %(name)s - %(message)s',
        handlers=[
            logging.FileHandler(path),
            logging.StreamHandler(sys.stdout)
        ])

    # get the port number
    try:
        port = int(args.port)
    except ValueError:
        print('The --port value must be an integer')
        return

    # get the password that is required for clients, servers and other network managers to connect
    password = None if args.password is None else ' '.join(args.password)

    # get the password to decrypt the private key
    key_password = None if args.key_password is None else ' '.join(args.key_password)

    # get the path to the certificate and to the private key
    cert, key = args.cert, args.key
    if cert is None and key is None:
        key = crypto.get_default_key_path()
        if not os.path.isfile(key):
            crypto.generate_key(key, password=key_password)
        cert = crypto.get_default_cert_path()
        if not os.path.isfile(cert):
            crypto.generate_certificate(cert, key_path=key, key_password=key_password)
    elif cert is None and key is not None:
        # create (or overwrite) the default certificate to match the key
        cert = crypto.generate_certificate(None, key_path=key, key_password=key_password)
    elif cert is not None and key is None:
        pass  # assume that the certificate file also contains the private key

    # start the network manager
    start_manager(password, port, cert, key, key_password, args.debug)
