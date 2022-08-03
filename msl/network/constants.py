"""
Constants that are used by the MSL-Network package.
"""
import os
import re
import sys
import socket
import subprocess

PORT = 1875
""":class:`int`: The default port number to use for the Network :class:`~msl.network.manager.Manager` 
(the year that the `BIPM <https://www.bipm.org/en/home>`_ was established)."""

HOSTNAME = socket.gethostname()
""":class:`str`: The hostname of the computer."""

# If this module is run via "sudo python" on a Raspberry Pi the value of
# os.path.expanduser('~') becomes '/root' instead of '/home/pi'. On Linux using
# "sudo python" keeps os.path.expanduser('~') as /home/<username> and running this
# module in an elevated command prompt on Windows keeps os.path.expanduser('~')
# as C:\\Users\\<username>. Therefore defining USER_DIR in the following way keeps
# things more consistent across more platforms.
USER_DIR = os.path.expanduser('~'+os.getenv('SUDO_USER', ''))

HOME_DIR = os.getenv('MSL_NETWORK_HOME', os.path.join(USER_DIR, '.msl', 'network'))
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

NOTIFICATION_UID = 'notification'

SHUTDOWN_SERVICE = 'shutdown_service'

SHUTDOWN_MANAGER = 'shutdown_manager'

try:
    IPV4_ADDRESSES = re.findall(
        (r'IPv4\sAddress.+:\s+' if IS_WINDOWS else r'inet\s+') +
        r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
        subprocess.check_output('ipconfig' if IS_WINDOWS else 'ip -4 address').decode()
    )
except (subprocess.CalledProcessError, OSError):
    IPV4_ADDRESSES = []

LOCALHOST_ALIASES = (
    HOSTNAME,
    'localhost',
    '127.0.0.1',
    '::1',
    '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa',
    '1.0.0.127.in-addr.arpa',
    *IPV4_ADDRESSES,
)
""":class:`tuple` of :class:`str`: Aliases for ``localhost``."""
