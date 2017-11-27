"""
Command line interface for the ``user`` command.
"""
import os

from .constants import DATABASE
from .database import UsersTable
from .utils import ensure_root_path

HELP = 'Add/remove a user into/from the Users table in a database.'

DESCRIPTION = HELP + """

The Network Manager can be started with the option to use a user's login
credentials as the authorisation check for a Client or Service to be able
to connect to the Network Manager.

To use the login credentials as the authentication check, start the Network
Manager with the --auth-login flag:

  msl-network start --auth-login
  
"""

EPILOG = """
Examples:

  # add 'j.doe' to the Users table  
  msl-network user add j.doe --password a good password

  # add 'a.smith' as an administrator to the Users table  
  msl-network user add a.smith --password !PaSsWoRd* --admin

  # update 'j.doe' to be an administrator  
  msl-network user update j.doe --admin

  # update the password for 'j.doe'  
  msl-network user update j.doe --password /path/to/my/password.txt

  # remove 'j.doe' from the Users table
  msl-network user remove j.doe

  # add 'j.doe' to the Users table in a specific database 
  msl-network user add j.doe --password The Password To Use --database path/to/database.db 

  # list all users in a Users table
  msl-network user list

"""


def add_parser_user(parser):
    """Add a ``user`` command to the parser."""
    p = parser.add_parser(
        'user',
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    p.add_argument(
        'action',
        choices=['insert', 'add', 'remove', 'delete', 'update', 'list'],
        help='The action to perform.'
    )
    p.add_argument(
        'username',
        nargs='?',
        help='The name of the user.'
    )
    p.add_argument(
        '-p', '--password',
        nargs='+',
        help='The password for the user (can contain spaces). Specify\n'
             'a path to a file if you do not want to type the password\n'
             'in the terminal (i.e., you do not want the password to\n'
             'appear in your command history). Whatever is written on\n'
             'the first line in the file will be used for the password.\n'
             'WARNING: If you enter a path that does not exist then the\n'
             'path itself will be used as the password.'
    )
    p.add_argument(
        '-a', '--admin',
        action='store_true',
        default=False,
        help='Pass in this flag if the user is an administrator.\n'
             'To remove administrative rights for a user run the\n'
             '"update" command for that user without the --admin flag.'
    )
    p.add_argument(
        '-d', '--database',
        help='The path to a database file to save the user credentials.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``user`` command."""
    database = DATABASE if args.database is None else args.database
    ensure_root_path(database)

    db = UsersTable(database=database)

    if args.action == 'list':
        users = db.users()
        width = len('Username')
        for name, _ in users:
            width = max(width, len(name))
        print('Users in ' + db.path + '\n')
        print('Username'.ljust(width) + ' Administrator')
        print('='*width + ' =============')
        for name, admin in users:
            print(name.ljust(width) + f' {admin}')
        return

    if args.username is None:
        print(f'ValueError: You must enter a username to {args.action}')
        return

    password = None if args.password is None else ' '.join(args.password)
    if password is not None and os.path.isfile(password):
        with open(password, 'r') as fp:
            password = fp.readline().strip()

    if args.action in ['insert', 'add']:
        if args.password is None:
            print(f'ValueError: You must enter a password for "{args.username}"')
            return
        try:
            db.insert(args.username, password, args.admin)
            print(f'{args.username} has been {args.action}ed')
        except ValueError as e:
            print(f'ValueError: {e}')
    elif args.action in ['remove', 'delete']:
        try:
            db.delete(args.username)
            print(f'{args.username} has been {args.action}d')
        except ValueError as e:
            print(f'ValueError: {e}')
    elif args.action == 'update':
        try:
            db.update(args.username, password=password, is_admin=args.admin)
            print(f'Updated {args.username}')
        except ValueError as e:
            print(f'ValueError: {e}')
    else:
        assert False, f'No action "{args.action}" is implemented'
