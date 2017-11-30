"""
Constants used by the MSL-Network package.
"""
import os
import enum
import socket

PORT = 1875
""":obj:`int`: The default port number to use (the year that the BIPM was established)."""

HOME_DIR = os.environ.get('MSL_HOME', os.path.join(os.path.expanduser('~'), '.msl', 'network'))
""":obj:`str`: The default $HOME directory where all files are to be located. 

Can be overwritten by specifying a ``MSL_HOME`` environment variable.
"""

CERT_DIR = os.path.join(HOME_DIR, 'certs')
""":obj:`str`: The default directory to save PEM certificates."""

KEY_DIR = os.path.join(HOME_DIR, 'keys')
""":obj:`str`: The default directory to save private PEM keys."""

DATABASE = os.path.join(HOME_DIR, 'manager.db')
""":obj:`str`: The default database path."""

HOSTNAME = socket.gethostname()
""":obj:`str`: The hostname of the Network Manager."""


class JSONPackage(enum.IntEnum):
    """Python packages for (de)serializing `JSON <http://www.json.org/>`_ data."""
    BUILTIN = 0
    ULTRA = 1  #: `UltraJSON <https://pypi.python.org/pypi/ujson>`_
    RAPID = 2  #: `RapidJSON <https://pypi.python.org/pypi/python-rapidjson>`_
    SIMPLE = 3  #: `simplejson <https://pypi.python.org/pypi/simplejson>`_
    YAJL = 4  #: `Yet-Another-Json-Library <https://pypi.python.org/pypi/yajl>`_


JSON = JSONPackage[os.environ.get('MSL_NETWORK_JSON', 'ULTRA').upper()]
""":obj:`int`: The Python package to use for (de)serializing `JSON <http://www.json.org/>`_ data.

Can be overwritten by specifying a ``MSL_NETWORK_JSON`` environment variable. 
Possible values are in :class:`JSONPackage`, for example, the 
``MSL_NETWORK_JSON`` environment variable can be defined to be ``ULTRA`` to use
`UltraJSON <https://pypi.python.org/pypi/ujson>`_ to (de)serialize JSON data.
"""
