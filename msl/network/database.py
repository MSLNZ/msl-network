"""
Databases that are used by the Network :class:`~msl.network.manager.Manager`.
"""
import os
import sqlite3
import logging
from datetime import datetime

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .constants import DATABASE
from .utils import (
    localhost_aliases,
    _is_manager_regex,
)

log = logging.getLogger(__name__)


class Database(object):

    def __init__(self, database, **kwargs):
        """Base class for connecting to a SQLite database.

        Automatically creates the database if does not already exist.

        Parameters
        ----------
        database : :class:`str`
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
        kwargs
            Optional keyword arguments to pass to :func:`sqlite3.connect`.
        """
        self._path = database if database is not None else DATABASE
        self._connection = None

        # open the connection to the database
        if self._path == ':memory:':
            log.debug('creating a database in RAM')
        elif not os.path.isfile(self._path):
            log.debug('creating a new database ' + self._path)
        else:
            log.debug('opening ' + self._path)

        if 'timeout' not in kwargs:
            kwargs['timeout'] = 60.0

        self._connection = sqlite3.connect(self._path, **kwargs)
        self._cursor = self._connection.cursor()

    @property
    def path(self):
        """:class:`str`: The path to the database file."""
        return self._path

    @property
    def connection(self):
        """:class:`sqlite3.Connection`: The connection object."""
        return self._connection

    @property
    def cursor(self):
        """:class:`sqlite3.Cursor`: The cursor object."""
        return self._cursor

    def __del__(self):
        self.close()

    def close(self):
        """Closes the connection to the database."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            log.debug('closed ' + self._path)

    def execute(self, sql, parameters=None):
        """Wrapper around :meth:`sqlite3.Cursor.execute`.

        Parameters
        ----------
        sql : :class:`str`
            The SQL command to execute
        parameters : :class:`list`, :class:`tuple` or :class:`dict`, optional
            Only required if the `sql` command is parameterized.
        """
        if parameters is None:
            log.debug(sql)
            self._cursor.execute(sql)
        else:
            log.debug(sql + ' {}'.format(parameters))
            self._cursor.execute(sql, parameters)

    def tables(self):
        """:class:`list` of :class:`str`: A list of the names of each table that is in the database."""
        self.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return sorted([t[0] for t in self._cursor.fetchall() if t[0] != 'sqlite_sequence'])

    def table_info(self, name):
        """Returns the information about each column in the specified table.

        Parameters
        ----------
        name : :class:`str`
            The name of the table to get the information of.

        Returns
        -------
        :class:`list` of :class:`tuple`
            The list of the fields in the table. The indices of each tuple correspond to:

            * 0 - id number of the column
            * 1 - the name of the column
            * 2 - the datatype of the column
            * 3 - whether or not a value in the column can be NULL (0 or 1)
            * 4 - the default value for the column
            * 5 - whether or not the column is used as a primary key (0 or 1)
        """
        self.execute("PRAGMA table_info('%s');" % name)
        return self._cursor.fetchall()

    def column_names(self, table_name):
        """Returns the names of the columns in the specified table.

        Parameters
        ----------
        table_name : :class:`str`
            The name of the table.

        Returns
        -------
        :class:`list` of :class:`str`
            A list of the names of each column in the table.
        """
        return [item[1] for item in self.table_info(table_name)]

    def column_datatypes(self, table_name):
        """Returns the datatype of each column in the specified table.

        Parameters
        ----------
        table_name : :class:`str`
            The name of the table.

        Returns
        -------
        :class:`list` of :class:`str`
            A list of the datatypes of each column in the table.
        """
        return [item[2] for item in self.table_info(table_name)]


class ConnectionsTable(Database):

    NAME = 'connections'
    """:class:`str`: The name of the table in the database."""

    def __init__(self, *, database=None, as_datetime=False, **kwargs):
        """The database table for devices that have connected to the Network
        :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        database : :class:`str`, optional
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
            If :data:`None` then loads the default database.
        as_datetime : :class:`bool`, optional
            Whether to fetch the timestamps from the database as :class:`datetime.datetime`
            objects. If :data:`False` then the timestamps will be of type :class:`str`.
        kwargs
            Optional keyword arguments to pass to :func:`sqlite3.connect`.
        """
        if as_datetime and 'detect_types' not in kwargs:
            kwargs['detect_types'] = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES

        super(ConnectionsTable, self).__init__(database, **kwargs)
        self.execute('CREATE TABLE IF NOT EXISTS %s ('
                     'pid INTEGER PRIMARY KEY AUTOINCREMENT, '
                     'timestamp TIMESTAMP NOT NULL, '
                     'ip_address TEXT NOT NULL, '
                     'domain TEXT NOT NULL, '
                     'port INTEGER NOT NULL, '
                     'message TEXT NOT NULL);' % self.NAME)
        self.connection.commit()

    def insert(self, peer, message):
        """Insert a message about what happened to the connection of the device.

        Parameters
        ----------
        peer : :class:`~msl.network.manager.Peer`
            The peer that connected to the Network :class:`~msl.network.manager.Manager`.
        message : :class:`str`
            The message about what happened.
        """
        self.execute('INSERT INTO %s VALUES(NULL, ?, ?, ?, ?, ?);' % self.NAME,
                     (datetime.now(), peer.ip_address, peer.domain, peer.port, message))
        self.connection.commit()

    def connections(self, *, timestamp1=None, timestamp2=None):
        """Returns all the connection records.

        Parameters
        ----------
        timestamp1 : :class:`datetime.datetime` or :class:`str`, optional
            Include all records that have a timestamp > `timestamp1`. If a
            :class:`str` then in the ``yyyy-mm-dd`` or ``yyyy-mm-dd HH:MM:SS`` format.
        timestamp2 : :class:`datetime.datetime` or :class:`str`, optional
            Include all records that have a timestamp < `timestamp2`. If a
            :class:`str` then in the ``yyyy-mm-dd`` or ``yyyy-mm-dd HH:MM:SS`` format.

        Returns
        -------
        :class:`list` of :class:`tuple`
            The connection records.
        """
        if timestamp1 is None and timestamp2 is None:
            self.execute('SELECT * FROM %s;' % self.NAME)
        elif timestamp1 is not None and timestamp2 is None:
            self.execute('SELECT * FROM %s WHERE timestamp > ?;' % self.NAME, (timestamp1,))
        elif timestamp1 is None and timestamp2 is not None:
            self.execute('SELECT * FROM %s WHERE timestamp < ?;' % self.NAME, (timestamp2,))
        else:
            self.execute('SELECT * FROM %s WHERE timestamp > ? AND timestamp < ?;' % self.NAME,
                         (timestamp1, timestamp2))
        return self.cursor.fetchall()


class HostnamesTable(Database):

    NAME = 'auth_hostnames'
    """:class:`str`: The name of the table in the database."""

    def __init__(self, *, database=None, **kwargs):
        """The database table for trusted hostname's that are allowed to connect
        to the Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        database : :class:`str`, optional
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
            If :data:`None` then loads the default database.
        kwargs
            Optional keyword arguments to pass to :func:`sqlite3.connect`.
       """
        super(HostnamesTable, self).__init__(database, **kwargs)
        self.execute('CREATE TABLE IF NOT EXISTS %s (hostname TEXT NOT NULL, UNIQUE(hostname));' % self.NAME)
        self.connection.commit()

        if not self.hostnames():
            for hostname in localhost_aliases():
                self.insert(hostname)

    def insert(self, hostname):
        """Insert the hostname.

        If the hostname is already in the table then it does not insert it again.

        Parameters
        ----------
        hostname : :class:`str`
            The trusted hostname.
        """
        self.execute('INSERT OR IGNORE INTO %s VALUES(?);' % self.NAME, (hostname,))
        self.connection.commit()

    def delete(self, hostname):
        """Delete the hostname.

        Parameters
        ----------
        hostname : :class:`str`
            The trusted hostname.

        Raises
        ------
        ValueError
            If `hostname` is not in the table.
        """
        # want to know if this hostname is not in the table
        if hostname not in self.hostnames():
            raise ValueError('Cannot delete "{}". This hostname is not in the table.'.format(hostname))
        self.execute('DELETE FROM %s WHERE hostname = ?;' % self.NAME, (hostname,))
        self.connection.commit()

    def hostnames(self):
        """:class:`list` of :class:`str`: Returns all the trusted hostnames."""
        self.execute('SELECT * FROM %s;' % self.NAME)
        return [item[0] for item in self.cursor.fetchall()]


class UsersTable(Database):

    NAME = 'auth_users'
    """:class:`str`: The name of the table in the database."""

    def __init__(self, *, database=None, **kwargs):
        """The database table for keeping information about a users login credentials
        for connecting to the Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        database : :class:`str`, optional
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
            If :data:`None` then loads the default database.
        kwargs
            Optional keyword arguments to pass to :func:`sqlite3.connect`.
        """
        super(UsersTable, self).__init__(database, **kwargs)
        self.execute('CREATE TABLE IF NOT EXISTS %s ('
                     'pid INTEGER PRIMARY KEY AUTOINCREMENT, '
                     'username TEXT NOT NULL, '
                     'key BLOB NOT NULL, '
                     'salt BLOB NOT NULL, '
                     'is_admin BOOLEAN NOT NULL, '
                     'UNIQUE(username));' % self.NAME)
        self.connection.commit()

        self._salt_size = 16
        self._length = 32
        self._iterations = 100000
        self._algorithm = hashes.SHA256()

    def insert(self, username, password, is_admin):
        """Insert a new user.

        The password is encrypted and stored in the database using PBKDF2_

        .. _PBKDF2: https://en.wikipedia.org/wiki/PBKDF2

        To update the values for a user use :meth:`update`.

        Parameters
        ----------
        username : :class:`str`
            The name of the user.
        password : :class:`str`
            The password of the user in plain-text format.
        is_admin : :class:`bool`
            Does this user have admin rights?

        Raises
        -------
        ValueError
            If the `username` is invalid or if `password` is empty.
        """
        if _is_manager_regex.search(username) is not None:
            raise ValueError('A username cannot end with ":<integer>"')
        if not password:
            raise ValueError('You must specify a password')

        salt = os.urandom(self._salt_size)
        kdf = PBKDF2HMAC(
            algorithm=self._algorithm,
            length=self._length,
            salt=salt,
            iterations=self._iterations,
            backend=default_backend()
        )
        key = kdf.derive(password.encode())
        try:
            self.execute('INSERT INTO %s VALUES(NULL, ?, ?, ?, ?);' % self.NAME, (username, key, salt, bool(is_admin)))
        except sqlite3.IntegrityError:
            raise ValueError('A user with the name "{}" already exists'.format(username)) from None
        self.connection.commit()

    def update(self, username, *, password=None, is_admin=None):
        """Update either the salt used for the password and/or the admin rights.

        Parameters
        ----------
        username : :class:`str`
            The name of the user.
        password : :class:`str`, optional
            The password of the user in plain-text format.
        is_admin : :class:`bool`, optional
            Does this user have admin rights?

        Raises
        ------
        ValueError
            If `username` is not in the table.
            If both `password` and `is_admin` are not specified.
            If `password` is an empty string.
        """
        self._ensure_user_exists(username, 'update')

        if password is None and is_admin is None:
            raise ValueError('Must specify either the password and/or the admin rights when updating')

        if password is None:
            self.execute('UPDATE %s SET is_admin=? WHERE username=?;' % self.NAME, (bool(is_admin), username))
            self.connection.commit()
            return

        if not password:
            raise ValueError('You must specify a password')

        salt = os.urandom(self._salt_size)
        key = PBKDF2HMAC(
            algorithm=self._algorithm,
            length=self._length,
            salt=salt,
            iterations=self._iterations,
            backend=default_backend()
        ).derive(password.encode())

        if is_admin is None:
            self.execute('UPDATE %s SET key=?, salt=? WHERE username=?;' % self.NAME,
                         (key, salt, username))
        else:
            self.execute('UPDATE %s SET key=?, salt=?, is_admin=? WHERE username=?;' % self.NAME,
                         (key, salt, bool(is_admin), username))

        self.connection.commit()

    def delete(self, username):
        """Delete the user.

        Parameters
        ----------
        username : :class:`str`
            The name of the user.

        Raises
        ------
        ValueError
            If `username` is not in the table.
        """
        self._ensure_user_exists(username, 'delete')
        self.execute('DELETE FROM %s WHERE username = ?;' % self.NAME, (username,))
        self.connection.commit()

    def get_user(self, username):
        """Get the information about a user.

        Parameters
        ----------
        username : :class:`str`
            The name of the user.

        Returns
        -------
        :class:`tuple`
            Returns (pid, username, key, salt, is_admin) for the specified `username`.
        """
        self.execute('SELECT * FROM %s WHERE username = ?;' % self.NAME, (username,))
        return self.cursor.fetchone()

    def records(self):
        """:class:`list` of :class:`tuple`: Returns [(pid, username, key, salt, is_admin), ...]
        for all users."""
        self.execute('SELECT * FROM %s;' % self.NAME)
        return self.cursor.fetchall()

    def usernames(self):
        """:class:`list` of :class:`str`: Returns the names of all registered users."""
        self.execute('SELECT username FROM %s;' % self.NAME)
        return [item[0] for item in self.cursor.fetchall()]

    def users(self):
        """:class:`list` of :class:`tuple`: Returns [(username, is_admin), ... ] for all users."""
        self.execute('SELECT username,is_admin FROM %s;' % self.NAME)
        return [(item[0], bool(item[1])) for item in self.cursor.fetchall()]

    def is_user_registered(self, username):
        """:class:`bool`: Whether `username` is a registered user."""
        self.execute('SELECT count(*) FROM %s WHERE username = ?;' % self.NAME, (username,))
        return bool(self.cursor.fetchone()[0])

    def is_password_valid(self, username, password):
        """Check whether the password matches the encrypted password in the database.

        Parameters
        ----------
        username : :class:`str`
            The name of the user.
        password : :class:`str`
            The password to check (in plain-text format).

        Returns
        -------
        :class:`bool`
            Whether `password` matches the password in the database for the user.
        """
        self.execute('SELECT key,salt FROM %s WHERE username = ?;' % self.NAME, (username,))
        key_salt = self._cursor.fetchone()
        if not key_salt:
            return False
        kdf = PBKDF2HMAC(
            algorithm=self._algorithm,
            length=self._length,
            salt=key_salt[1],
            iterations=self._iterations,
            backend=default_backend()
        )
        try:
            kdf.verify(password.encode(), key_salt[0])
            return True
        except InvalidKey:
            return False

    def is_admin(self, username):
        """Check whether a user has admin rights.

        Parameters
        ----------
        username : :class:`str`
            The name of the user.

        Returns
        -------
        :class:`bool`
            Whether the user has admin rights.
        """
        self.execute('SELECT is_admin FROM %s WHERE username = ?;' % self.NAME, (username,))
        user = self.cursor.fetchone()
        if user:
            return bool(user[0])
        return False

    def _ensure_user_exists(self, username, action):
        # want to know if this user is not in the table
        if username not in self.usernames():
            raise ValueError('Cannot {} "{}". This user is not in the table.'.format(action, username))
