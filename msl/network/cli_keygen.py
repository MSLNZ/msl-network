"""
Command line interface for the ``keygen`` command.

To see the help documentation, run the following command in a terminal::

   msl-network keygen --help

"""
import os

from .cryptography import generate_key

HELP = 'Generates a private key to digitally sign a PEM certificate.'

DESCRIPTION = HELP + """

The keygen command is similar to the openssl command::

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
        '--curve',
        default='SECP384R1',
        help='The name of the elliptic curve to use. Only used if the\n'
             'encryption algorithm is ECC. Default is %(default)s.'
    )
    p.add_argument(
        '--password',
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
        '--path',
        help='The path to where to save the private key\n'
             '(e.g., --path /where/to/save/key.pem). If omitted then\n'
             'the default directory and filename is used to save the\n'
             'private key file.'
    )
    p.add_argument(
        '--size',
        default=2048,
        help='The size (number of bits) of the key. Only used if the\n'
             'encryption algorithm is RSA or DSA. Default is %(default)s.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``keygen`` command."""
    try:
        size = int(args.size)
    except ValueError:
        print('ValueError: The --size value must be an integer')
        return

    password = None if args.password is None else ' '.join(args.password)
    if password is not None and os.path.isfile(password):
        print('Reading the password from the file')
        with open(password, 'r') as fp:
            password = fp.readline().strip()

    path = generate_key(
        path=args.path,
        algorithm=args.algorithm,
        password=password,
        size=size,
        curve=args.curve
    )

    print('Created private {} key {}'.format(args.algorithm.upper(), path))

