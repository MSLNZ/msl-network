"""
Command line interface for the ``start`` command.
"""
from .constants import PORT


HELP = 'Start the asynchronous network manager.'

DESCRIPTION = HELP + """
"""

EXAMPLE = """
Examples:
    # start the network manager using the default settings
    msl-network start

    # start the network manager on port 8326
    msl-network start --port 8326
    
    # require a password for clients, servers and other network managers 
    # to be able to connect to this network manager
    msl-network start --password abc 123

    # use a specific certificate and key for connections to the manager 
    msl-network start --cert-path path/to/cert.pem --key-path path/to/key.pem
"""


def add_parser_start(parser):
    """Add a ``start`` command to the parser."""
    p = parser.add_parser(
        'start',
        help=HELP,
        description=DESCRIPTION,
        epilog=EXAMPLE,
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
        help='The password (passphrase) to use to decrypt the\n'
             'private key. If omitted and the key is encrypted then\n'
             'you will be asked for the password to decrypt the key.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``start`` command."""
    print('TODO: create the start module', args)
