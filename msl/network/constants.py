"""
Constants used by the MSL-Network package.
"""
import os
import socket

PORT = 1875
""":obj:`int`: The default port number to use (the year that the BIPM was established)."""

HOME_DIR = os.environ.get('MSL_HOME', os.path.join(os.path.expanduser('~'), '.msl', 'network'))
""":obj:`str`: The default $HOME directory where all files are to be located. 

Can be overwritten by specifying a ``MSL_HOME`` environment variable
for the operating system.
"""

CERT_DIR = os.path.join(HOME_DIR, 'certs')
""":obj:`str`: The default directory to save PEM certificates."""

KEY_DIR = os.path.join(HOME_DIR, 'keys')
""":obj:`str`: The default directory to save private PEM keys."""

DATABASE = os.path.join(HOME_DIR, 'manager.db')
""":obj:`str`: The default database path."""

HOSTNAME = socket.gethostname()
""":obj:`str`: The hostname of the Network Manager."""
