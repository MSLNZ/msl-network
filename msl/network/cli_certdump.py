"""
Command line interface for the ``certdump`` command.

To see the help documentation, run the following command in a terminal::

   msl-network certdump --help

"""
import os

from .utils import ensure_root_path
from .cryptography import (
    get_metadata_as_string,
    load_certificate,
)

HELP = 'Dumps the details of a PEM certificate.'

DESCRIPTION = HELP + """

The ``certdump`` command is similar to the openssl command to
get the details of a certificate::
    
  openssl x509 -in certificate.crt -text -noout
  
"""

EPILOG = """
Examples::

  # dump the details to the terminal
  msl-network certdump /path/to/cert.pem 

  # dump the details to a file
  msl-network certdump /path/to/cert.pem --out dump.txt

See Also::

  msl-network certgen
  
"""

__doc__ += DESCRIPTION + EPILOG


def add_parser_certdump(parser):
    """Add the ``certdump`` command to the `parser`."""
    p = parser.add_parser(
        'certdump',
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    p.add_argument(
        'certfile',
        help='The path to a PEM certificate.'
    )
    p.add_argument(
        '-o', '--out',
        help='The file path to dump the details to. If omitted\n'
             'then prints the details to the terminal.'
    )
    p.set_defaults(func=execute)


def execute(args):
    """Executes the ``certdump`` command."""

    if not os.path.isfile(args.certfile):
        print(f'Cannot find {args.certfile}')
        return

    meta = get_metadata_as_string(load_certificate(args.certfile))

    if args.out is None:
        print(meta)
    else:
        ensure_root_path(args.out)
        with open(args.out, mode='wt') as fp:
            fp.write(f'Certificate details for {args.certfile}\n')
            fp.write(meta)
        print(f'Dumped the certificate details to {args.out}')
