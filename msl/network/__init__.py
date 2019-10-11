"""
Concurrent and asynchronous network I/O.
"""
import re
from collections import namedtuple

from .client import (
    connect,
    LinkedClient,
    filter_client_connect_kwargs,
)
from .service import (
    Service,
    filter_service_start_kwargs,
)
from .exceptions import MSLNetworkError
from .database import (
    ConnectionsTable,
    HostnamesTable,
    UsersTable,
)
from .manager import (
    run_services,
    filter_run_forever_kwargs,
)

__author__ = 'Measurement Standards Laboratory of New Zealand'
__copyright__ = '\xa9 2017 - 2019, ' + __author__
__version__ = '0.5.0.dev0'

_v = re.search(r'(\d+)\.(\d+)\.(\d+)[.-]?(.*)', __version__).groups()

version_info = namedtuple('version_info', 'major minor micro releaselevel')(int(_v[0]), int(_v[1]), int(_v[2]), _v[3])
""":obj:`~collections.namedtuple`: Contains the version information as a (major, minor, micro, releaselevel) tuple."""
