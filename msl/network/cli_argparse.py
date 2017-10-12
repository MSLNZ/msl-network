"""
Custom argument parser.
"""
import argparse


class ArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        """A custom argument parser."""
        kwargs['add_help'] = False  # use a custom help message (see below)
        kwargs['formatter_class'] = argparse.RawTextHelpFormatter
        super(ArgumentParser, self).__init__(*args, **kwargs)

        self.add_argument(
            '-h', '--help',
            action='help',
            help='Show this help message and exit.',
            default=argparse.SUPPRESS
        )
