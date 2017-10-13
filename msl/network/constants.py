"""
Constants used by the MSL-Network package.
"""
import os

PORT = 1875
""":obj:`int`: The default port number to use (the year that the BIPM was established)."""

HOME_DIR = os.path.join(os.path.expanduser('~'), '.msl')
""":obj:`str`: The default $HOME directory."""

CERT_DIR = os.path.join(HOME_DIR, 'certs')
""":obj:`str`: The default directory to save PEM certificates."""

KEY_DIR = os.path.join(HOME_DIR, 'keys')
""":obj:`str`: The default directory to save private PEM keys."""
