"""
An asynchronous network manager.
"""
from collections import namedtuple

from .client import Client
from .service import Service
from .connection import connect
from .database import ConnectionsDatabase, AuthenticateDatabase

__author__ = 'Joseph Borbely'
__copyright__ = '\xa9 2017, ' + __author__
__version__ = '0.1.0'

version_info = namedtuple('version_info', 'major minor micro')(*map(int, __version__.split('.')[:3]))
""":obj:`~collections.namedtuple`: Contains the version information as a (major, minor, micro) tuple."""
