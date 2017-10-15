"""
Command line interface for the ``certgen`` command.
"""
from . import crypto

HELP = 'Generate a self-signed PEM certificate.'

DESCRIPTION = HELP + """

The certgen command is similar to the openssl command to generate a 
self-signed certificate from a pre-existing private key

  openssl req -key private.key -new -x509 -days 365 -out certificate.crt  
"""

EPILOG = """
Examples:
  # create a default certificate using a default private key
  # and save it to the default directory
  msl-network certgen 

  # create a certificate using the specified key and 
  # save the certificate to the specified file
  msl-network certgen --key-path /path/to/key.pem /path/to/cert.pem

See Also: 
  msl-network keygen
  msl-network certdump  
"""


def add_parser_certgen(parser):
    """Add a ``certgen`` command to the parser."""
    p = parser.add_parser(
        'certgen',
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
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
             'the certificate. If omitted then load (or create) a\n'
             'default key. See also: msl-network keygen'
    )
    p.add_argument(
        '--key-password',
        nargs='+',
        help='The password (passphrase) to use to decrypt the\n'
             'private key. Only required if --key-path is specified\n'
             'and it is an encrypted file.'
    )
    p.add_argument(
        '--algorithm',
        default='SHA256',
        help='The hash algorithm to use. Default is %(default)s.'
    )
    p.add_argument(
        '--years-valid',
        default=100,
        help='The number of years that the certificate is valid for\n'
             '(e.g., a value of 0.25 would mean that the certificate\n'
             'is valid for 3 months). Default is %(default)s years.'
    )
    p.add_argument(
        '--show',
        action='store_true',
        default=False,
        help='Display the details of the newly-created certificate.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``certgen`` command."""
    try:
        years = float(args.years_valid)
    except ValueError:
        print('The --years-valid value must be a decimal number')
        return

    password = None if args.key_password is None else ' '.join(args.key_password)

    path = crypto.generate_certificate(
        args.path,
        key_path=args.key_path,
        key_password=password,
        algorithm=args.algorithm,
        years_valid=years
    )

    print('Created the self-signed certificate ' + path)
    if args.show:
        print('')
        print(crypto.get_details(crypto.load_certificate(path)))
