"""
Command line interface for the ``certgen`` command.

To see the help documentation, run the following command in a terminal::

   msl-network certgen --help

"""
import os

from . import cryptography
from .constants import DEFAULT_YEARS_VALID

HELP = 'Generate a self-signed PEM certificate.'

DESCRIPTION = HELP + """

The certificate uses the hostname of the computer that this command was
executed on as the Common Name and as the Issuer Name.

The ``certgen`` command is similar to the openssl command to generate a 
self-signed certificate from a pre-existing private key::

  openssl req -key private.key -new -x509 -days 365 --out certificate.crt
 
"""

EPILOG = """
Examples::

  # create a default certificate using the default private key
  # and save it to the default directory
  msl-network certgen 

  # create a certificate using the specified key and 
  # save the certificate to the specified file
  msl-network certgen --key-file /path/to/key.pem /path/to/cert.pem

See Also::

  msl-network keygen
  msl-network certdump
 
"""

__doc__ += DESCRIPTION + EPILOG


def add_parser_certgen(parser):
    """Add the ``certgen`` command to the `parser`."""
    p = parser.add_parser(
        'certgen',
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    p.add_argument(
        'out',
        nargs='?',
        help='The path to save the certificate to\n'
             '(e.g., /where/to/save/cert.pem). If omitted then\n'
             'the default directory and filename is used to\n'
             'save the certificate file.'
    )
    p.add_argument(
        '-a', '--algorithm',
        default='SHA256',
        help='The hash algorithm to use. Default is %(default)s.'
    )
    p.add_argument(
        '-k', '--key-file',
        help='The path to the private key to use to digitally sign\n'
             'the certificate. If omitted then load (or create) a\n'
             'default key. See also: msl-network keygen'
    )
    p.add_argument(
        '-p', '--key-file-password',
        nargs='+',
        help='The password to use to decrypt the private key. Only\n'
             'required if --key-file is specified and it is an encrypted\n'
             'file. Specify a path to a file if you do not want to type\n'
             'the password in the terminal (i.e., you do not want the\n'
             'password to appear in your command history). Whatever is\n'
             'written on the first line in the file will be used for the\n'
             'password. WARNING: If you enter a path that does not exist\n'
             'then the path itself will be used as the password.'
    )
    p.add_argument(
        '-y', '--years-valid',
        default=DEFAULT_YEARS_VALID,
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
        if years <= 0:
            raise ValueError
    except ValueError:
        print('ValueError: The --years-valid value must be a positive number')
        return

    key_file_password = None if args.key_file_password is None else ' '.join(args.key_file_password)
    if key_file_password is not None and os.path.isfile(key_file_password):
        print('Reading the key password from the file')
        with open(key_file_password, mode='rt') as fp:
            key_file_password = fp.readline().strip()

    try:
        path = cryptography.generate_certificate(
            path=args.out,
            key_path=args.key_file,
            key_password=key_file_password,
            algorithm=args.algorithm,
            years_valid=years
        )
    except Exception as e:
        print('{}: {}'.format(e.__class__.__name__, e))
        return

    print('Created the self-signed certificate {!r}'.format(path))
    if args.show:
        print('')
        print(cryptography.get_metadata_as_string(cryptography.load_certificate(path)))
