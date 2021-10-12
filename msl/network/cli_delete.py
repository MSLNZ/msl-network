"""
Command line interface for the ``delete`` command.

.. versionadded:: 1.0

To see the help documentation, run the following command in a terminal::

   msl-network delete --help

"""
import os

from .constants import HOME_DIR

HELP = 'Delete files that are created by MSL-Network.'

DESCRIPTION = HELP + """

Can remove the database, log files, certificates and/or keys. 

"""

EPILOG = """
Examples::

  # delete all files that are created by MSL-Network
  msl-network delete --all 

  # delete all log files 
  msl-network delete --logs

"""

__doc__ += DESCRIPTION + EPILOG


def add_parser_delete(parser):
    """Add the ``delete`` command to the `parser`."""
    p = parser.add_parser(
        'delete',
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    p.add_argument(
        '-a', '--all',
        action='store_true',
        default=False,
        help='Delete all files that are created by MSL-Network.'
    )
    p.add_argument(
        '-c', '--certs',
        action='store_true',
        default=False,
        help='Delete all certificates.'
    )
    p.add_argument(
        '-d', '--database',
        action='store_true',
        default=False,
        help='Delete the database.'
    )
    p.add_argument(
        '-k', '--keys',
        action='store_true',
        default=False,
        help='Delete all keys.'
    )
    p.add_argument(
        '-l', '--logs',
        action='store_true',
        default=False,
        help='Delete all log files.'
    )
    p.add_argument(
        '-r', '--root',
        help='The root directory to where the database and folders\n'
             'are located. If omitted then the default directory\n'
             'is used.'
    )
    p.add_argument(
        '-q', '--quiet',
        action='store_true',
        default=False,
        help='Whether to suppress messages written to stdout.'
    )
    p.add_argument(
        '-y', '--yes',
        action='store_true',
        default=False,
        help='Do not ask for confirmation before deleting.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``delete`` command."""

    def stdout(message, end='\n'):
        # print a message to stdout only if not in quiet mode
        if args.quiet:
            return
        print(message, end=end)

    def proceed():
        # returns a bool for whether to proceed with the deletion
        if args.yes:
            return True
        yn = input('Proceed ([y]/n)? ')
        if not yn or yn.lower() in ['y', 'yes']:
            return True
        stdout('Okay, not deleting')
        return False

    def human_size(file_size):
        # returns a file size as a human-readable string
        if file_size < 1e3:
            return '{} B'.format(file_size)
        if file_size < 1e6:
            return '{} kB'.format(round(file_size/1e3))
        if file_size < 1e9:
            return '{} MB'.format(round(file_size/1e6))
        return '{} GB'.format(round(file_size/1e9))

    def delete(path):
        # try to delete the file
        try:
            os.remove(path)
            stdout('Deleted: {}'.format(path))
        except OSError as e:
            stdout('OSError: {} -- Cannot delete {}'.format(e, path))

    def search(directory, extn):
        # find all files in a directory
        files = []
        total_size = 0
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if not filename.endswith(extn):
                    continue
                f = os.path.join(root, filename)
                files.append(f)
                total_size += os.path.getsize(f)
        return files, human_size(total_size)

    if not any([args.all, args.certs, args.database, args.keys, args.logs]):
        stdout('You must specify what you want to delete, for example')
        stdout('  msl-network delete --keys')
        return

    root_dir = args.root or HOME_DIR
    if not os.path.isdir(root_dir):
        stdout('The {!r} directory does not exist'.format(root_dir))
        return

    if args.all or args.database:
        database = os.path.join(root_dir, 'manager.sqlite3')
        if os.path.isfile(database):
            size = os.path.getsize(database)
            stdout('\nThe following database will be deleted:')
            stdout('  {} [{}]'.format(database, human_size(size)))
            if proceed():
                delete(database)
        else:
            stdout('No database file found')

    if args.all or args.certs:
        stdout('\nSearching for certificates ... ', end='')
        certs, human = search(os.path.join(root_dir, 'certs'), '.crt')
        if certs:
            stdout('\n  {} certificate(s) will be deleted [{}]'.format(len(certs), human))
            if proceed():
                for file in certs:
                    delete(file)
        else:
            stdout('no certificates found')

    if args.all or args.keys:
        stdout('\nSearching for keys ... ', end='')
        keys, human = search(os.path.join(root_dir, 'keys'), '.key')
        if keys:
            stdout('\n  {} key(s) will be deleted [{}]'.format(len(keys), human))
            if proceed():
                for file in keys:
                    delete(file)
        else:
            stdout('no keys found')

    if args.all or args.logs:
        stdout('\nSearching for log files ... ', end='')
        logs, human = search(os.path.join(root_dir, 'logs'), '.log')
        if logs:
            stdout('\n  {} log file(s) will be deleted [{}]'.format(len(logs), human))
            if proceed():
                for file in logs:
                    delete(file)
        else:
            stdout('no log files found')
