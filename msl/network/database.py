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
from .utils import localhost_aliases

log = logging.getLogger(__name__)


class Database(object):

    def __init__(self, database, **kwargs):
        """Base class for connecting to a SQLite database.

        Automatically creates the database if does not already exist.

        Parameters
        ----------
        database : :obj:`str`
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
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

        self._connection = sqlite3.connect(self._path, **kwargs)
        self._connection.row_factory = sqlite3.Row
        self._cursor = self._connection.cursor()

    @property
    def path(self):
        """:obj:`str`: The path to the database file."""
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
        """Closes the connection to the database.

        .. note::
           The connection to the database is automatically closed when
           the :class:`Database` object gets destroyed (the reference count is 0).
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            log.debug('closed ' + self._path)

    def execute(self, sql, parameters=None):
        """Wrapper around :meth:`sqlite3.Cursor.execute`.

        Parameters
        ----------
        sql : :obj:`str`
            The SQL command to execute
        parameters : :obj:`list`, :obj:`tuple` or :obj:`dict`, optional
            Only required if the `sql` command is parameterized.
        """
        if parameters is None:
            log.debug(sql)
            self._cursor.execute(sql)
        else:
            log.debug(f'{sql} {parameters}')
            self._cursor.execute(sql, parameters)

    def tables(self):
        """:obj:`list` of :obj:`str`: A list of the table names that are in the database."""
        self.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [t[0] for t in self._cursor.fetchall() if t[0] != 'sqlite_sequence']

    def table_info(self, name):
        """Returns the information about each column in the specified table.

        Parameters
        ----------
        name : :obj:`str`
            The name of the table to get the information of.

        Returns
        -------
        :obj:`list` of :class:`sqlite3.Row`
            A list of the fields in the table.

            The keys of each returned :class:`sqlite3.Row` item are:

            * **cid** - id of the column
            * **name** - the name of the column
            * **type** - the datatype of the column
            * **notnull** - whether or not a value in the column can be NULL (0 or 1)
            * **dflt_value** - the default value for the column
            * **pk** - whether or not the column is used as a primary key (0 or 1)
        """
        self.execute("PRAGMA table_info('%s');" % name)
        return self._cursor.fetchall()

    def column_names(self, table_name):
        """Returns the names of the columns in the specified table.

        Parameters
        ----------
        table_name : :obj:`str`
            The name of the table.

        Returns
        -------
        :obj:`list` of :obj:`str`
            A list of the names of the columns in the table.
        """
        return [item['name'] for item in self.table_info(table_name)]

    def column_datatypes(self, table_name):
        """Returns the datatype of each column in the specified table.

        Parameters
        ----------
        table_name : :obj:`str`
            The name of the table.

        Returns
        -------
        :obj:`list` of :obj:`str`
            A list of the datatype of each column in the table
        """
        return [item['type'] for item in self.table_info(table_name)]


class ConnectionsTable(Database):

    NAME = 'connections'
    """:obj:`str`: The name of the table in the database."""

    def __init__(self, database=None, **kwargs):
        """Database for devices that have connected to the Network
        :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        database : :obj:`str`, optional
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
            If :obj:`None` then loads the default database.
        """
        super(ConnectionsTable, self).__init__(database, **kwargs)
        self.execute('CREATE TABLE IF NOT EXISTS %s ('
                     'pid INTEGER PRIMARY KEY AUTOINCREMENT, '
                     'datetime TEXT NOT NULL, '
                     'address TEXT NOT NULL, '
                     'name TEXT NOT NULL, '
                     'port INTEGER NOT NULL, '
                     'message TEXT NOT NULL);' % self.NAME)
        self.connection.commit()

    def insert(self, peer, message):
        """Insert a message about what happened to the connection of the peer.

        Parameters
        ----------
        peer : :class:`~msl.network.manager.Peer`
            The peer that connected to the Network :class:`~msl.network.manager.Manager`
        message : :obj:`str`
            The message about what happened.
        """
        self.execute('INSERT INTO %s VALUES(NULL, ?, ?, ?, ?, ?);' % self.NAME,
                     (datetime.now(), peer.ip_address, peer.domain, peer.port, message))
        self.connection.commit()

    def connections(self, json_safe=True):
        """Returns all the connection records.

        Parameters
        ----------
        json_safe : :obj:`bool`
            Whether to return the results as a JSON-serializable object.
            If :obj:`False` then the values in the datetime column are converted
            to :class:`datetime.datetime` objects.

        Returns
        -------
        :obj:`list` of :obj:`tuple`
            The connection records.
        """
        self.execute('SELECT * FROM %s;' % self.NAME)
        if json_safe:
            return [tuple(item) for item in self.cursor.fetchall()]
        else:
            return [(r[0], datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S.%f'), r[2], r[3], r[4], r[5])
                    for r in self.cursor.fetchall()]


class HostnamesTable(Database):

    NAME = 'hostnames'
    """:obj:`str`: The name of the table in the database."""

    def __init__(self, database=None, **kwargs):
        """Database for trusted hostname's that are allowed to connect
        to the Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        database : :obj:`str`, optional
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
            If :obj:`None` then loads the default database.
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
        hostname : :obj:`str`
            The trusted hostname.
        """
        self.execute('INSERT OR IGNORE INTO %s VALUES(?);' % self.NAME, (hostname,))
        self.connection.commit()

    def delete(self, hostname):
        """Delete the hostname.

        Parameters
        ----------
        hostname : :obj:`str`
            The trusted hostname.

        Raises
        ------
        ValueError
            If `hostname` is not in the table.
        """
        # want to know if this hostname is not in the table
        if hostname not in self.hostnames():
            raise ValueError(f'Cannot delete "{hostname}". This hostname is not in the table.')
        self.execute('DELETE FROM %s WHERE hostname = ?;' % self.NAME, (hostname,))
        self.connection.commit()

    def hostnames(self):
        """:obj:`list` of :obj:`str`: Returns all the trusted hostnames."""
        self.execute('SELECT * FROM %s;' % self.NAME)
        return [h[0] for h in self.cursor.fetchall()]


class UsersTable(Database):

    NAME = 'users'
    """:obj:`str`: The name of the table in the database."""

    def __init__(self, database=None, **kwargs):
        """Database for keeping information about a users login and admin rights
        for connecting to the Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        database : :obj:`str`, optional
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
            If :obj:`None` then loads the default database.
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

        Parameters
        ----------
        username : :obj:`str`
            The name of the user.
        password : :obj:`str`
            The password of the user in plain-text format.
        is_admin : :obj:`bool`
            Does this user have admin rights?

        Raises
        -------
        ValueError
            If a user with `username` already exists in the table. To update the values
            for a user use :meth:`.update`. Or if the password is empty.
        """
        if not password:
            raise ValueError('The password cannot be an empty string')

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
            raise ValueError(f'A user with the name "{username}" already exists') from None
        self.connection.commit()

    def update(self, username, *, password=None, is_admin=None):
        """Update either the salt used for the password and/or the admin rights.

        Parameters
        ----------
        username : :obj:`str`
            The name of the user.
        password : :obj:`str`, optional
            The salt to use for decrypting the password with PBKDF2_
        is_admin : :obj:`bool`, optional
            Does this user have admin rights?

        .. _PBKDF2: https://en.wikipedia.org/wiki/PBKDF2

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
            self.execute('UPDATE %s SET username=?, is_admin=? WHERE username=?;' % self.NAME,
                         (username, bool(is_admin), username))
            self.connection.commit()
            return

        if not password:
            raise ValueError('The password cannot be an empty string')

        salt = os.urandom(self._salt_size)
        key = PBKDF2HMAC(
            algorithm=self._algorithm,
            length=self._length,
            salt=salt,
            iterations=self._iterations,
            backend=default_backend()
        ).derive(password.encode())

        if is_admin is None:
            self.execute('UPDATE %s SET username=?, key=?, salt=? WHERE username=?;' % self.NAME,
                         (username, key, salt, username))
        else:
            self.execute('UPDATE %s SET username=?, key=?, salt=?, is_admin=? WHERE username=?;' % self.NAME,
                         (username, key, salt, bool(is_admin), username))

        self.connection.commit()

    def delete(self, username):
        """Delete the user.

        Parameters
        ----------
        username : :obj:`str`
            The name of the user.

        Raises
        ------
        ValueError
            If `username` is not in the table.
        """
        self._ensure_user_exists(username, 'update')
        self.execute('DELETE FROM %s WHERE username = ?;' % self.NAME, (username,))
        self.connection.commit()

    def get_user(self, username):
        """Get the information about a user.

        Parameters
        ----------
        username : :obj:`str`
            The name of the user.

        Returns
        -------
        :class:`sqlite3.Row`
            The information about the user.
        """
        self.execute('SELECT * FROM %s WHERE username = ?;' % self.NAME, (username,))
        return self.cursor.fetchone()

    def records(self):
        """:obj:`list` of :class:`sqlite3.Row`: Returns the information about all users."""
        self.execute('SELECT * FROM %s;' % self.NAME)
        return self.cursor.fetchall()

    def usernames(self):
        """:obj:`list` of :class:`str`: Returns a list of all usernames."""
        self.execute('SELECT username FROM %s;' % self.NAME)
        return [item['username'] for item in self.cursor.fetchall()]

    def users(self):
        """:obj:`list` of :class:`tuple`: Returns [(username, is_admin), ... ] for all users."""
        self.execute('SELECT username,is_admin FROM %s;' % self.NAME)
        return [(item['username'], bool(item['is_admin'])) for item in self.cursor.fetchall()]

    def is_password_valid(self, username, password):
        """Check whether the password matches the encrypted password in the database.

        Parameters
        ----------
        username : :obj:`str`
            The name of the user.
        password : :obj:`str`
            The password to check (in plain-text format).

        Returns
        -------
        :obj:`bool`
            Whether `password` matches the password in the database for the user.
        """
        user = self.get_user(username)
        if not user:
            return False
        kdf = PBKDF2HMAC(
            algorithm=self._algorithm,
            length=self._length,
            salt=user['salt'],
            iterations=self._iterations,
            backend=default_backend()
        )
        try:
            kdf.verify(password.encode(), user['key'])
            return True
        except InvalidKey:
            return False

    def is_admin(self, username):
        """Check whether a user has admin rights.

        Parameters
        ----------
        username : :obj:`str`
            The name of the user.

        Returns
        -------
        :obj:`bool`
            Whether the user has admin rights.
        """
        user = self.get_user(username)
        if user:
            return bool(user['is_admin'])
        return False

    def _ensure_user_exists(self, username, action):
        # want to know if this user is not in the table
        if username not in self.usernames():
            raise ValueError(f'Cannot {action} "{username}". This user is not in the table.')
