"""
Command line interface for the ``auth`` command.
"""
from .utils import ensure_root_path
from .constants import DATABASE_PATH
from .database import AuthenticateDatabase

HELP = 'Add/remove hostname(s) into/from an authentication table in a database.'

DESCRIPTION = HELP + """

Each hostname in an authentication table is considered as a trusted device 
and therefore the device can connect to the network manager.
"""

EPILOG = """
Examples:
  
  # add '192.168.1.100' to the list of trusted devices that can connect to the network manager  
  msl-network auth add 192.168.1.100

  # remove '192.168.1.100' and '192.168.1.110' from the list of trusted devices
  msl-network auth remove 192.168.1.100 192.168.1.110

  # add '192.168.1.100' to the authentication table in a specific database 
  msl-network auth add 192.168.1.100 --path path/to/database.db 
  
  # list all trusted hosts
  msl-network auth list

"""


def add_parser_auth(parser):
    """Add a ``auth`` command to the parser."""
    p = parser.add_parser(
        'auth',
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    p.add_argument(
        'action',
        choices=['insert', 'add', 'remove', 'delete', 'list'],
        help='The action to perform.'
    )
    p.add_argument(
        'hostname',
        nargs='*',
        help='The hostname of the trusted device.'
    )
    p.add_argument(
        '--database',
        help='The path to a database file.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``auth`` command."""
    database = DATABASE_PATH if args.database is None else args.database
    ensure_root_path(database)

    db = AuthenticateDatabase(database)

    if args.action == 'list':
        print('Trusted devices in ' + db.path)
        print('\nHostnames:')
        for hostname in sorted(db.hostnames()):
            print('  ' + hostname)
    elif args.action in ['insert', 'add']:
        for name in args.hostname:
            db.insert(name)
    elif args.action in ['remove', 'delete']:
        for name in args.hostname:
            db.delete(name)
    else:
        assert False, f'No action "{args.action}" is implemented'
