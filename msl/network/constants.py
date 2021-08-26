"""
Constants that are used by the MSL-Network package.
"""
import os
import sys
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

TERMINATION = b'\r\n'
""":class:`bytes`: The sequence of bytes that signify the end of the data being sent.

.. versionadded:: 0.6
"""

ENCODING = 'utf-8'
""":class:`str`: The encoding to use to convert :class:`str` to :class:`bytes`.

.. versionadded:: 0.6
"""

