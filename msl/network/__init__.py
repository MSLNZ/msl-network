"""
Concurrent and asynchronous network I/O.
"""
from collections import namedtuple

from .client import connect
from .service import Service
from .database import ConnectionsTable, HostnamesTable, UsersTable

__author__ = 'Joseph Borbely'
__copyright__ = '\xa9 2017 - 2018, ' + __author__
__version__ = '0.2.0.dev0'

version_info = namedtuple('version_info', 'major minor micro')(*map(int, __version__.split('.')[:3]))
""":obj:`~collections.namedtuple`: Contains the version information as a (major, minor, micro) tuple."""
