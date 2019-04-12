"""
Command line interface for the ``start`` command.

To see the help documentation, run the following command in a terminal::

   msl-network start --help

"""
from . import manager
from .constants import PORT

HELP = 'Start the MSL Network Manager.'

DESCRIPTION = HELP + """
"""

EPILOG = """
Examples::

  # start the Network Manager using the default settings
  msl-network start

  # start the Network Manager on port 8326
  msl-network start --port 8326
    
  # require an authentication password for Clients and Services 
  # to be able to connect to the Network Manager 
  msl-network start --auth-password abc 123

  # use a specific certificate and key for the secure TLS protocol 
  msl-network start --certfile /path/to/cert.pem --keyfile /path/to/key.pem

  # require that a valid username and password are specified for 
  # Clients and Services to be able to connect to the Network Manager 
  msl-network start --auth-login
    
See Also::

  msl-network certgen
  msl-network keygen
  msl-network hostname
  msl-network user
  
"""

__doc__ += DESCRIPTION + EPILOG


def add_parser_start(parser):
    """Add the ``start`` command to the `parser`."""
    p = parser.add_parser(
        'start',
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    p.add_argument(
        '--auth-hostname',
        action='store_true',
        default=False,
        help='Only connections from trusted hostnames are allowed.\n'
             'See also: msl-network hostname'
    )
    p.add_argument(
        '--auth-login',
        action='store_true',
        default=False,
        help='Each connection to the Network Manager must login by\n'
             'specifying a username and password. See also: msl-network user'
    )
    p.add_argument(
        '-P', '--auth-password',
        nargs='+',
        help='Use a password for all Clients and Services to be able to\n'
             'connect to the Network Manager. The password can contain\n'
             'spaces. Using this type of authentication can be thought of\n'
             'as using a global password that can easily be changed every\n'
             'time the Network Manager starts. Specify a path to a file\n'
             'if you do not want to type the password in the terminal\n'
             '(i.e., you do not want the password to appear in your command\n'
             'history). Whatever is written on the first line in the file\n'
             'will be used for the password. WARNING: If you enter a path\n'
             'that does not exist then the path itself will be used as the\n'
             'password.'
    )
    p.add_argument(
        '-c', '--certfile',
        help='The path to a certificate file to use for the secure TLS\n'
             'connection. If omitted then a default certificate is used.\n'
             'See also: msl-network certgen'
    )
    p.add_argument(
        '-d', '--database',
        help='The path to the database to use for logging network connections\n'
             'and to use for the --auth-hostname and --auth-login flags. If\n'
             'omitted then the default database is used.'
    )
    p.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Enable DEBUG logging messages. On Windows, enabling debug mode\n'
             'also allows for the CTRL+C interrupt to stop the event loop.'
    )
    p.add_argument(
        '--disable-tls',
        action='store_true',
        default=False,
        help='Start the Network Manager without using the TLS protocol.'
    )
    p.add_argument(
        '-k', '--keyfile',
        help='The path to the private key which was used to digitally\n'
             'sign the certificate. If omitted then the default key is\n'
             'used. If --certfile is omitted and --keyfile is specified then\n'
             'this key is used to create (or overwrite) the default\n'
             'certificate and this new certificate will be used for the\n'
             'secure TLS connection. See also: msl-network keygen'
    )
    p.add_argument(
        '-D', '--keyfile-password',
        nargs='+',
        help='The password to use to decrypt the private key. Only required\n'
             'if the key file is encrypted. Specify a path to a file if you\n'
             'do not want to type the password in the terminal (i.e., you do\n'
             'not want the password to appear in your command history).\n'
             'Whatever is written on the first line in the file will be used\n'
             'for the password. WARNING: If you enter a path that does not\n'
             'exist then the path itself will be used as the password.'
    )
    p.add_argument(
        '-p', '--port',
        default=PORT,
        help='The port number to use for the Network Manager.\n'
             'Default is %(default)s.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``start`` command."""
    kwargs = vars(args)
    kwargs.pop('cmd', None)
    kwargs.pop('func', None)
    manager.run_forever(**kwargs)
