"""
Main entry point to the asynchronous network manager via the command-line interface (CLI).
"""
import sys

from . import __version__

PARSER = None

DESCRIPTION = """An asynchronous network manager.

The manager allows for multiple clients, servers and other managers to connect
to it and links a clients request to the appropriate server/manager to handle 
the request and then sends the response back to the client.
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

    PARSER = ArgumentParser(description=DESCRIPTION)

    PARSER.add_argument(
        '-V', '--version',
        action='version',
        version='{}'.format(__version__),
        help='Show the version number and exit.'
    )

    command_parser = PARSER.add_subparsers(
        metavar='command',
        dest='cmd',
    )
    # http://bugs.python.org/issue9253
    # http://stackoverflow.com/a/18283730/1599393
    command_parser.required = True

    add_parser_certgen(command_parser)
    add_parser_keygen(command_parser)
    add_parser_start(command_parser)

    return PARSER


def main(*args):
    """
    Main entry point to the asynchronous network manager.
    """
    parser = configure_parser()
    if not args:
        args = sys.argv[1:]
    args = parser.parse_args(args)
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
