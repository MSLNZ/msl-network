"""
Command line interface for the ``certgen`` command.
"""

HELP = 'Generate a self-signed certificate to use for the SSL/TLS protocol.'

DESCRIPTION = HELP + """
"""

EXAMPLE = """
Examples:
    # create a default certificate using a default private key
    msl-network certgen 

    # create a certificate using the specified key and 
    # save the certificate to the specified file
    msl-network certgen --key-path /path/to/key.pem /path/to/cert.pem  
"""


def add_parser_certgen(parser):
    """Add a ``certgen`` command to the parser."""
    p = parser.add_parser(
        'certgen',
        help=HELP,
        description=DESCRIPTION,
        epilog=EXAMPLE,
    )
    p.add_argument(
        'path',
        nargs='?',
        help='The path to where to save the certificate\n'
             '(e.g., /where/to/save/cert.pem). If omitted then\n'
             'the default directory and filename is used.'
    )
    p.add_argument(
        '--key-path',
        help='The path to the private key to use to digitally sign\n'
             'the certificate. If omitted then load/create the\n'
             'default key. See also: msl-network keygen'
    )
    p.add_argument(
        '--key-password',
        nargs='+',
        help='The password (passphrase) to use to decrypt the\n'
             'private key. Only required if --key-path is specified\n'
             'and it is an encrypted file.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``certgen`` command."""
    print('TODO: create the certgen module', args)
