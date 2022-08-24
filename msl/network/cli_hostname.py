"""
Command line interface for the ``hostname`` command.

To see the help documentation, run the following command in a terminal::

   msl-network hostname --help

"""
from .constants import DATABASE
from .database import HostnamesTable
from .utils import ensure_root_path

HELP = 'Add/remove hostname(s) into/from the table in the database.'

DESCRIPTION = HELP + """

The Network Manager can be started with the option to use trusted devices 
(based on the hostname of the connecting device) as the authorisation check
for a Client or Service to be able to connect to the Network Manager.

Each hostname in the table is considered as a trusted device and therefore
the device can connect to the Network Manager.

To use trusted hostnames as the authentication check, start the Network
Manager with the ``--auth-hostname`` flag::

  msl-network start --auth-hostname

"""

EPILOG = """
Examples::
  
  # add 'TheHostname' as a trusted device in the default database
  msl-network hostname add TheHostname

  # add 'TheHostname' and 'OtherHostname' as trusted devices  
  msl-network hostname add TheHostname OtherHostname

  # remove 'OtherHostname' from the database of trusted devices
  msl-network hostname remove OtherHostname

  # add 'TheHostname' to a specific database 
  msl-network hostname add TheHostname --database /path/to/database.db 
  
  # list all trusted hostnames
  msl-network hostname list

"""

__doc__ += DESCRIPTION + EPILOG


def add_parser_hostname(parser):
    """Add the ``hostname`` command to the `parser`."""
    p = parser.add_parser(
        'hostname',
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
        'names',
        nargs='*',
        help='The hostname of trusted devices.'
    )
    p.add_argument(
        '-d', '--database',
        help='The path to a database file to save the trusted hostname to.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``hostname`` command."""
    database = DATABASE if args.database is None else args.database
    ensure_root_path(database)

    db = HostnamesTable(database=database)

    if args.action == 'list':
        print(f'Trusted devices in {db.path}')
        print('\nHostnames:')
        for hostname in db.hostnames():
            print(f'  {hostname}')
    elif args.action in ['insert', 'add']:
        if not args.names:
            print(f'No hostnames were {args.action}ed')
            return
        for name in args.names:
            db.insert(name)
            print(f'{args.action.title()}ed {name}')
    elif args.action in ['remove', 'delete']:
        if not args.names:
            print(f'No hostnames were {args.action}d')
            return
        for name in args.names:
            try:
                db.delete(name)
            except ValueError:
                print(f'Cannot {args.action} {name!r}. This hostname is not in the table.')
            else:
                print(f'{args.action.title()}d {name}')
    else:
        assert False, f'No action {args.action!r} is implemented'
