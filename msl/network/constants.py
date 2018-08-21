"""
Constants used by the **MSL-Network** package.
"""
import os
import enum
import socket

PORT = 1875
""":class:`int`: The default port number to use for the Network :class:`~msl.network.manager.Manager` 
(the year that the `BIPM <https://www.bipm.org/en/about-us/>`_ was established)."""

HOSTNAME = socket.gethostname()
""":class:`str`: The hostname of the Network :class:`~msl.network.manager.Manager`."""

HOME_DIR = os.environ.get('MSL_NETWORK_HOME', os.path.join(os.path.expanduser('~'), '.msl', 'network'))
""":class:`str`: The default $HOME directory where all files are to be located. 

Can be overwritten by specifying a ``MSL_NETWORK_HOME`` environment variable.
"""

CERT_DIR = os.path.join(HOME_DIR, 'certs')
""":class:`str`: The default directory to save PEM certificates."""

KEY_DIR = os.path.join(HOME_DIR, 'keys')
""":class:`str`: The default directory to save private PEM keys."""

DATABASE = os.path.join(HOME_DIR, 'manager.sqlite3')
""":class:`str`: The default database path."""


class JSONPackage(enum.Enum):
    """
    Python packages for (de)serializing `JSON <https://www.json.org/>`_ data.

    .. _UltraJSON: https://pypi.python.org/pypi/ujson
    .. _RapidJSON: https://pypi.python.org/pypi/python-rapidjson
    .. _simplejson: https://pypi.python.org/pypi/simplejson
    .. _Yet-Another-Json-Library: https://pypi.python.org/pypi/yajl
    """
    BUILTIN = 'BUILTIN'
    ULTRA = 'ULTRA'  #: UltraJSON_
    RAPID = 'RAPID'  #: RapidJSON_
    SIMPLE = 'SIMPLE'  #: simplejson_
    YAJL = 'YAJL'  #: Yet-Another-Json-Library_


JSON = JSONPackage[os.environ.get('MSL_NETWORK_JSON', 'BUILTIN').upper()]
""":class:`str`: The Python package to use for (de)serializing JSON_ data.

By default, the builtin :mod:`json` module is used. 

To change which JSON_ package to use you can specify a ``MSL_NETWORK_JSON`` 
environment variable. Possible values are in :class:`JSONPackage`. For example,
setting ``MSL_NETWORK_JSON=ULTRA`` would use UltraJSON_ to (de)serialize JSON_ data.
"""
