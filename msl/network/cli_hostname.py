"""
Command line interface for the ``hostname`` command.

To see the help documentation, run the following command in a terminal::

   msl-network hostname --help

"""
from .constants import DATABASE
from .utils import ensure_root_path
from .database import HostnamesTable

HELP = 'Add/remove hostname(s) into/from an auth_hostnames table in a database.'

DESCRIPTION = HELP + """

The Network Manager can be started with the option to use trusted devices 
(based on the hostname of the connecting device) as the authorisation check
for a Client or Service to be able to connect to the Network Manager.

Each hostname in the auth_hostnames table is considered as a trusted device 
and therefore the device can connect to the Network Manager.

To use trusted hostnames as the authentication check, start the Network
Manager with the --auth-hostname flag::

  msl-network start --auth-hostname

"""

EPILOG = """
Examples::
  
  # add 'TheHostname' to the list of trusted devices
  msl-network hostname add TheHostname

  # add 'TheHostname' and 'OtherHostname' to the list of trusted devices  
  msl-network hostname add TheHostname OtherHostname

  # remove 'OtherHostname' from the list of trusted devices
  msl-network hostname remove OtherHostname

  # add 'TheHostname' to the auth_hostnames table in a specific database 
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
        print('Trusted devices in ' + db.path)
        print('\nHostnames:')
        for hostname in sorted(db.hostnames()):
            print('  ' + hostname)
    elif args.action in ['insert', 'add']:
        if not args.names:
            print('No hostnames were ' + args.action + 'ed')
        else:
            for name in args.names:
                db.insert(name)
                print(args.action.title() + 'ed ' + name)
    elif args.action in ['remove', 'delete']:
        if not args.names:
            print('No hostnames were ' + args.action + 'd')
        else:
            for name in args.names:
                try:
                    db.delete(name)
                    print(args.action.title() + 'd ' + name)
                except ValueError as e:
                    print(e)
    else:
        assert False, 'No action "' + args.action + '" is implemented'
