"""
Main entry point to MSL-Network via the command-line interface (CLI).
"""
import sys

from . import __version__

PARSER = None

DESCRIPTION = """A concurrent Network Manager.

The Network Manager allows for multiple Clients and Services to connect to 
it and links a Client's request to the appropriate Service to handle 
the request and then the Network Manager sends the response from the Service
back to the Client.
"""


def configure_parser():
    """:class:`~msl.network.cli_argparse.ArgumentParser`: Returns the argument parser."""

    # pretty much mimics the ArgumentParser structure used by conda

    global PARSER
    if PARSER is not None:
        return PARSER

    from .cli_argparse import ArgumentParser
    from .cli_certgen import add_parser_certgen
    from .cli_keygen import add_parser_keygen
    from .cli_start import add_parser_start
    from .cli_certdump import add_parser_certdump
    from .cli_hostname import add_parser_hostname
    from .cli_user import add_parser_user
    from .cli_delete import add_parser_delete

    PARSER = ArgumentParser(description=DESCRIPTION)

    PARSER.add_argument(
        '-V', '--version',
        action='version',
        version=f'{__version__}',
        help='Show the version number and exit.'
    )

    command_parser = PARSER.add_subparsers(
        metavar='command',
        dest='cmd',
    )
    # https://bugs.python.org/issue9253
    # https://stackoverflow.com/a/18283730/1599393
    command_parser.required = True

    add_parser_certdump(command_parser)
    add_parser_certgen(command_parser)
    add_parser_delete(command_parser)
    add_parser_hostname(command_parser)
    add_parser_keygen(command_parser)
    add_parser_start(command_parser)
    add_parser_user(command_parser)

    return PARSER


def main(*args):
    """
    Main entry point to MSL-Network via the command-line interface (CLI).
    """
    if not args:
        args = sys.argv[1:]
        if not args:
            args = ['--help']
    parser = configure_parser()
    args = parser.parse_args(args)
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
