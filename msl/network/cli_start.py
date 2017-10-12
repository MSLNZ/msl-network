"""
Command line interface for the ``start`` command.
"""
from .constants import PORT


HELP = 'Start an asynchronous network manager.'

DESCRIPTION = HELP + """
"""

EXAMPLE = """
Examples:
    # start the network manager using the default settings
    msl-network start

    # start the network manager on port 8326
    msl-network start --port 8326
    
    # require a password for clients/servers to connect to the network manager
    msl-network start --password abc 123
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
        '--cert-path',
        help='The path to a X.509 certificate file to use for the\n'
             'secure TLS connection. If not specified then the\n'
             'default certificate is loaded.'
    )
    p.add_argument(
        '--key-path',
        help='The path to the private key which was used to sign the\n'
             'certificate. If not specified then load the default key.\n'
             'If --cert-path is omitted and --key-path is specified then\n'
             'this key will be used to generate a new default certificate.\n'
             'See also: msl-network keygen'
    )
    p.add_argument(
        '--password',
        nargs='+',
        help='The password (passphrase) that is required for a client\n'
             'or server to be able to connect to the network manager.\n'
             'Default is None (i.e., an empty string).'
    )
    p.add_argument(
        '--port',
        default=PORT,
        help='The port number to use for the network manager.\n'
             'Default is {}.'.format(PORT)
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``start`` command."""
    print('TODO: create the start module', args)
