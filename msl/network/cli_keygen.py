"""
Command line interface for the ``keygen`` command.
"""

HELP = 'Generate a private key that can be used to digitally sign a certificate.'

DESCRIPTION = HELP + """

See also: msl-network certgen
"""

EXAMPLE = """
Examples:
    # create a default private key (RSA, 2048-bit, unencrypted)
    msl-network keygen 

    # create a 4096-bit, encrypted private key using the DSA algorithm
    msl-network keygen dsa --size 4096 --password WhatEVER you wAnt! 
"""


def add_parser_keygen(parser):
    """Add a ``keygen`` command to the parser."""
    p = parser.add_parser(
        'keygen',
        help=HELP,
        description=DESCRIPTION,
        epilog=EXAMPLE,
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
        '--password',
        nargs='+',
        help='The password (passphrase) to use to encrypt the private\n'
             'key. Can include spaces. Default is None (unencrypted).'
    )
    p.add_argument(
        '--path',
        help='The path to where to save the private key\n'
             '(e.g., --path where/to/save/key.pem). If omitted then\n'
             'the default directory and filename is used.'
    )
    p.add_argument(
        '--size',
        default=2048,
        help='The size (number of bits) of the key. Only used if the\n'
             'encryption algorithm is "rsa" or "dsa". Recommended to be\n'
             'either 2048 or 4096. Default is %(default)s.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``keygen`` command."""
    print('TODO: create the keygen module', args)
