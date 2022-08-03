"""
Command line interface for the ``user`` command.

To see the help documentation, run the following command in a terminal::

   msl-network user --help

"""
import os

from .constants import DATABASE
from .database import UsersTable
from .utils import ensure_root_path

HELP = 'Add/remove a user into/from a database.'

DESCRIPTION = HELP + """

The Network Manager can be started with the option to use a user's login
credentials as the authorisation check for a Client or Service to be able
to connect to the Network Manager.

To use the login credentials as the authentication check, start the Network
Manager with the ``--auth-login`` flag::

  msl-network start --auth-login
  
"""

EPILOG = """
Examples::

  # add 'j.doe' to the default database  
  msl-network user add j.doe --password a good password

  # add 'a.smith' as an administrator to the database  
  msl-network user add a.smith --password !PaSsWoRd* --admin

  # update 'j.doe' to be an administrator  
  msl-network user update j.doe --admin

  # update 'a.smith' to not be an administrator  
  msl-network user update a.smith

  # update the password for 'j.doe' using a password in a file 
  msl-network user update j.doe --password /path/to/my/password.txt

  # remove 'j.doe' from the default database
  msl-network user remove j.doe

  # add 'j.doe' to a specific database 
  msl-network user add j.doe --password The Password To Use --database /path/to/database.db 

  # list all users in the database
  msl-network user list

"""

__doc__ += DESCRIPTION + EPILOG


def add_parser_user(parser):
    """Add the ``user`` command to the `parser`."""
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
    p.add_argument(
        '-p', '--password',
        nargs='+',
        help='The password for the user (can contain spaces). Specify\n'
             'a path to a file if you do not want to type the password\n'
             'in the terminal (i.e., you do not want the password to\n'
             'appear in your command history). Whatever is written on\n'
             'the first line in the file will be used for the password.\n'
             'WARNING: If you specify a path that does not exist then the\n'
             'path itself will be used as the password.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``user`` command."""
    database = DATABASE if args.database is None else args.database
    ensure_root_path(database)

    db = UsersTable(database=database)

    if args.action == 'list':
        users = db.users()
        if not users:
            print('There are no users in the database')
            return

        width = len('Username')
        for name, _ in users:
            width = max(width, len(name))
        print(f'Users in {db.path}\n')
        print('Username'.ljust(width) + ' Administrator')
        print('='*width + ' =============')
        for name, admin in users:
            print(f'{name.ljust(width)} {admin}')
        return

    if args.username is None:
        print(f'ValueError: You must specify a username to {args.action}')
        return

    password = None if args.password is None else ' '.join(args.password)
    if password is not None and os.path.isfile(password):
        print('Reading the password from the file')
        with open(password, mode='rt') as fp:
            password = fp.readline().strip()

    if args.action in ['insert', 'add']:
        try:
            db.insert(args.username, password, args.admin)
        except ValueError as e:
            print(f'ValueError: {e}')
        else:
            print(f'{args.username} has been {args.action}ed')
    elif args.action in ['remove', 'delete']:
        try:
            db.delete(args.username)
        except ValueError:
            print(f'ValueError: Cannot {args.action} {args.username!r}. '
                  f'This user is not in the table.')
        else:
            print(f'{args.username} has been {args.action}d')
    elif args.action == 'update':
        try:
            db.update(args.username, password=password, is_admin=args.admin)
        except ValueError as e:
            print(f'ValueError: {e}')
        else:
            print(f'Updated {args.username}')
    else:
        assert False, f'No action {args.action!r} is implemented'
