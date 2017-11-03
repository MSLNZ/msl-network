"""
Command line interface for the ``auth`` command.
"""
from .constants import DATABASE_PATH
from .database import AuthenticateDatabase

HELP = 'Insert/delete hostname(s) into/from an authentication table in a database.'

DESCRIPTION = HELP + """

Each hostname in an authentication table is considered as a trusted device 
and therefore the device can connect to the network manager.
"""

EPILOG = """
Examples:
  
  # insert 'localhost' to the list of trusted devices that can connect to the network manager  
  msl-network auth insert localhost

  # delete 'localhost' and '127.0.0.1' from the list of trusted devices
  msl-network auth delete localhost 127.0.0.1

  # insert 'localhost' to a specific database 
  msl-network auth insert localhost --path path/to/database.db 

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
        'hostnames',
        nargs='*',
        help='The hostnames.'
    )
    p.add_argument(
        '--database',
        help='The path to a database file.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``auth`` command."""
    database = DATABASE_PATH if args.database is None else args.database
    db = AuthenticateDatabase(database)

    if args.action == 'list':
        print('Trusted devices in ' + db.path)
        print('\nHostnames:')
        for hostname in sorted(db.hostnames()):
            print('  ' + hostname)
    elif args.action in ['insert', 'add']:
        for name in args.hostnames:
            db.insert(name)
    elif args.action in ['remove', 'delete']:
        for name in args.hostnames:
            db.delete(name)
    else:
        assert False, 'No action "{}" is implemented'.format(args.action)
