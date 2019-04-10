"""
Command line interface for the ``start`` command.

To see the help documentation, run the following command in a terminal::

   msl-network start --help

"""
import os
import sys
import logging
from datetime import datetime

from . import cryptography, manager
from .utils import ensure_root_path
from .constants import HOME_DIR, PORT, DATABASE
from .database import HostnamesTable, UsersTable

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
  msl-network start --cert /path/to/cert.pem --key /path/to/key.pem

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
        '--auth-password',
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
        '--cert',
        help='The path to a certificate file to use for the secure TLS\n'
             'connection. If omitted then a default certificate is used.\n'
             'See also: msl-network certgen'
    )
    p.add_argument(
        '--database',
        help='The path to the database to use for logging network connections\n'
             'and to use for the --auth-hostname and --auth-login flags. If\n'
             'omitted then the default database is used.'
    )
    p.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='Enable DEBUG logging messages.'
    )
    p.add_argument(
        '--disable-tls',
        action='store_true',
        default=False,
        help='Start the Network Manager without using the TLS protocol.'
    )
    p.add_argument(
        '--key',
        help='The path to the private key which was used to digitally\n'
             'sign the certificate. If omitted then the default key is\n'
             'used. If --cert is omitted and --key is specified then\n'
             'this key is used to create (or overwrite) the default\n'
             'certificate and this new certificate will be used for the\n'
             'secure TLS connection. See also: msl-network keygen'
    )
    p.add_argument(
        '--key-password',
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
        '--port',
        default=PORT,
        help='The port number to use for the Network Manager.\n'
             'Default is %(default)s.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``start`` command."""

    # set up logging -- FileHandler and StreamHandler
    now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    path = os.path.join(HOME_DIR, 'logs', 'manager-{}.log'.format(now))
    ensure_root_path(path)

    # the root logger is a FileHandler and it will always log at the debug level
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)-8s] %(name)s - %(message)s',
        filename=path,
    )

    # the StreamHandler log level can be decided from the command line
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.DEBUG if args.debug else logging.INFO)
    sh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-5s] %(name)s - %(message)s'))
    logging.getLogger().addHandler(sh)

    # get the port number
    try:
        port = int(args.port)
    except ValueError:
        print('ValueError: The port number must be an integer')
        return

    if not args.disable_tls:
        # get the password to decrypt the private key
        key_password = None if args.key_password is None else ' '.join(args.key_password)
        if key_password is not None and os.path.isfile(key_password):
            with open(key_password, 'r') as fp:
                key_password = fp.readline().strip()

        # get the path to the certificate and to the private key
        cert, key = args.cert, args.key
        if cert is None and key is None:
            key = cryptography.get_default_key_path()
            if not os.path.isfile(key):
                cryptography.generate_key(path=key, password=key_password)
            cert = cryptography.get_default_cert_path()
            if not os.path.isfile(cert):
                cryptography.generate_certificate(path=cert, key_path=key, key_password=key_password)
        elif cert is None and key is not None:
            # create (or overwrite) the default certificate to match the key
            cert = cryptography.generate_certificate(key_path=key, key_password=key_password)
        elif cert is not None and key is None:
            pass  # assume that the certificate file also contains the private key
    else:
        cert, key, key_password = None, None, None

    # get the path to the database file
    if args.database is not None and os.path.isfile(args.database):
        database = args.database
    else:
        database = DATABASE

    # check which authentication method to use
    login = None
    password = None
    hostnames = None
    if args.auth_password is None and not args.auth_hostname and not args.auth_login:
        # then no authentication is required for Clients or Services to connect to the Manager
        pass
    elif args.auth_password is not None and not args.auth_hostname and not args.auth_login:
        # then the authentication is a password.
        password = ' '.join(args.auth_password)
        if os.path.isfile(password):
            with open(password, 'r') as fp:
                password = fp.readline().strip()
    elif args.auth_password is None and args.auth_hostname and not args.auth_login:
        # then the authentication is based on a list of trusted hosts
        hostnames = HostnamesTable(database=database).hostnames()
    elif args.auth_password is None and not args.auth_hostname and args.auth_login:
        # then the authentication is based on the user's login information
        login = True
        table = UsersTable(database=database)
        if not table.usernames():
            table.close()
            print('ValueError: The Users table is empty. No one could login...')
            print('To add a user to the Users table run the "msl-network user" command')
            return
        table.close()
    else:
        print('ValueError: Cannot specify multiple authentication methods')
        return

    # start the network manager
    manager.start(port=port, password=password, login=login, hostnames=hostnames,
                  database=database, debug=args.debug, disable_tls=args.disable_tls,
                  certfile=cert, keyfile=key, keyfile_password=key_password)
