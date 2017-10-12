"""
Command line interface for the ``keygen`` command.
"""

HELP = 'Generate a private RSA key.'

DESCRIPTION = HELP + """
"""

EXAMPLE = """
Examples:
    # create a default private key
    msl-network keygen 

    # create a 2048-bit, encrypted private key in the default path.
    msl-network keygen --size 2048 --password WhatEVER you wAnt! 
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
        '--password',
        nargs='+',
        help='The password (passphrase) to use to encrypt the\n'
             'private key. Can include spaces.'
    )
    p.add_argument(
        '--path',
        help='The path to where to save the private key\n'
             '(e.g., --path where/to/save/key.pem). If omitted then\n'
             'a default directory and filename is used.'
    )
    p.add_argument(
        '--size',
        default=4096,
        help='The size (number of bits) of the key.\n'
             'Recommend to be 2048 or 4096.\n'
             'Default is 4096.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``keygen`` command."""
    print('TODO: create the keygen module', args)
