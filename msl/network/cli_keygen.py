"""
Command line interface for the ``keygen`` command.

To see the help documentation, run the following command in a terminal::

   msl-network keygen --help

"""
import os

from .cryptography import generate_key

HELP = 'Generate a private key to digitally sign a PEM certificate.'

DESCRIPTION = HELP + """

The ``keygen`` command is similar to the openssl command::

  openssl req -newkey rsa:2048 -nodes -keyout key.pem
    
"""

EPILOG = """
Examples::

  # create a default private key (RSA, 2048-bit, unencrypted)
  # and save it to the default directory
  msl-network keygen 

  # create a 3072-bit, encrypted private key using the DSA algorithm
  msl-network keygen dsa --size 3072 --password WhatEVER you wAnt!

See Also::

  msl-network certgen
  
"""

__doc__ += DESCRIPTION + EPILOG


def add_parser_keygen(parser):
    """Add the ``keygen`` command to the `parser`."""
    p = parser.add_parser(
        'keygen',
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    p.add_argument(
        'algorithm',
        default='rsa',
        nargs='?',
        choices=['rsa', 'dsa', 'ecc'],
        help='The encryption algorithm to use to generate the private\n'
             'key. Default is %(default)s.'
    )
    p.add_argument(
        '-c', '--curve',
        default='SECP384R1',
        help='The name of the elliptic curve to use. Only used if the\n'
             'encryption algorithm is ECC. Default is %(default)s.'
    )
    p.add_argument(
        '-p', '--password',
        nargs='+',
        help='The password to use to encrypt the private key. Can include\n'
             'spaces. Default is None (unencrypted). Specify a path to a\n'
             'file if you do not want to type the password in the terminal\n'
             '(i.e., you do not want the password to appear in your command\n'
             'history). Whatever is written on the first line in the file\n'
             'will be used for the password. WARNING: If you enter a path\n'
             'that does not exist then the path itself will be used as the\n'
             'password.'
    )
    p.add_argument(
        '-o', '--out',
        help='The path to save the private key to\n'
             '(e.g., --out /where/to/save/key.pem). If omitted then\n'
             'the default directory and filename is used to save the\n'
             'private key file.'
    )
    p.add_argument(
        '-s', '--size',
        default=2048,
        help='The size (number of bits) of the key. Only used if the\n'
             'encryption algorithm is RSA or DSA. Default is %(default)s.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``keygen`` command."""
    try:
        size = int(args.size)
        if size <= 0:
            raise ValueError
    except ValueError:
        print('ValueError: The --size value must be a positive integer')
        return

    password = None if args.password is None else ' '.join(args.password)
    if password is not None and os.path.isfile(password):
        print('Reading the key password from the file')
        with open(password, mode='rt') as fp:
            password = fp.readline().strip()

    try:
        path = generate_key(
            path=args.out,
            algorithm=args.algorithm,
            password=password,
            size=size,
            curve=args.curve
        )
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        return

    print('Created private {} key {!r}'.format(args.algorithm.upper(), path))
