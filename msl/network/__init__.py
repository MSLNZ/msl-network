"""
Concurrent and asynchronous network I/O.
"""
import re
from collections import namedtuple

from .client import LinkedClient
from .client import connect
from .client import filter_client_connect_kwargs
from .database import ConnectionsTable
from .database import HostnamesTable
from .database import UsersTable
from .manager import filter_run_forever_kwargs
from .manager import run_services
from .service import Service
from .service import filter_service_start_kwargs

__author__ = 'Measurement Standards Laboratory of New Zealand'
__copyright__ = '\xa9 2017 - 2023, ' + __author__
__version__ = '1.0.1.dev0'

_v = re.search(r'(\d+)\.(\d+)\.(\d+)[.-]?(.*)', __version__).groups()

version_info = namedtuple('version_info', 'major minor micro releaselevel')(int(_v[0]), int(_v[1]), int(_v[2]), _v[3])
""":obj:`~collections.namedtuple`: Contains the version information as a (major, minor, micro, releaselevel) tuple."""
