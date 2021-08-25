"""
Constants used by the **MSL-Network** package.
"""
import os
import sys
import enum
import socket

PORT = 1875
""":class:`int`: The default port number to use for the Network :class:`~msl.network.manager.Manager` 
(the year that the `BIPM <https://www.bipm.org/en/about-us/>`_ was established)."""

HOSTNAME = socket.gethostname()
""":class:`str`: The hostname of the Network :class:`~msl.network.manager.Manager`."""

# If this module is run via "sudo python" on a Raspberry Pi the value of
# os.path.expanduser('~') becomes '/root' instead of '/home/pi'. On Linux using
# "sudo python" keeps os.path.expanduser('~') as /home/<username> and running this
# module in an elevated command prompt on Windows keeps os.path.expanduser('~')
# as C:\\Users\\<username>. Therefore defining USER_DIR in the following way keeps
# things more consistent across more platforms.
USER_DIR = os.path.expanduser('~'+os.getenv('SUDO_USER', ''))

HOME_DIR = os.environ.get('MSL_NETWORK_HOME', os.path.join(USER_DIR, '.msl', 'network'))
""":class:`str`: The default directory where all files are to be located. 

Can be overwritten by specifying a ``MSL_NETWORK_HOME`` environment variable.
"""

CERT_DIR = os.path.join(HOME_DIR, 'certs')
""":class:`str`: The default directory to save PEM certificates."""

KEY_DIR = os.path.join(HOME_DIR, 'keys')
""":class:`str`: The default directory to save private PEM keys."""

DATABASE = os.path.join(HOME_DIR, 'manager.sqlite3')
""":class:`str`: The default database path."""

IS_WINDOWS = sys.platform == 'win32'
""":class:`bool`: Whether the operating system is Windows."""

DISCONNECT_REQUEST = '__disconnect__'

DEFAULT_YEARS_VALID = 100 if sys.maxsize > 2**32 else 15

NETWORK_MANAGER_RUNNING_PREFIX = 'Network Manager running on'

NOTIFICATION_UUID = 'notification'

SHUTDOWN_SERVICE = 'shutdown_service'

SHUTDOWN_MANAGER = 'shutdown_manager'


class JSONPackage(enum.Enum):
    """
    Python packages for (de)serializing `JSON <https://www.json.org/>`_ data.

    .. _UltraJSON: https://pypi.python.org/pypi/ujson
    .. _RapidJSON: https://pypi.python.org/pypi/python-rapidjson
    .. _simplejson: https://pypi.python.org/pypi/simplejson
    .. _Yet-Another-Json-Library: https://pypi.python.org/pypi/yajl

    .. versionchanged:: 0.6
       Added ``UJSON`` as an alias for UltraJSON_.

    """
    BUILTIN = 'BUILTIN'
    ULTRA = 'ULTRA'  #: UltraJSON_
    UJSON = 'ULTRA'  #: UltraJSON_
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
