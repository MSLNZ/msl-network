"""
Databases that are used by the Network :class:`~msl.network.manager.Manager`.
"""
import os
import sqlite3
import logging
from datetime import datetime

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
        self._path = database
        self._connection = None

        # open the connection to the database
        if database == ':memory:':
            log.debug('creating a database in RAM')
        elif not os.path.isfile(database):
            log.debug('creating a new database ' + database)
        else:
            log.debug('opening ' + database)

        self._connection = sqlite3.connect(database, **kwargs)
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
           the :class:`Database` object gets destroyed.
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


class ConnectionsDatabase(Database):

    NAME = 'connections'
    """:obj:`str`: The name of the table in the database."""

    def __init__(self, database, **kwargs):
        """Database for devices that have connected to the Network
        :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        database : :obj:`str`
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
        """
        super().__init__(database, **kwargs)
        self.execute('CREATE TABLE IF NOT EXISTS %s ('
                     'pid INTEGER PRIMARY KEY AUTOINCREMENT, '
                     'datetime TEXT, '
                     'host TEXT, '
                     'port INTEGER, '
                     'action TEXT);' % self.NAME)
        self.connection.commit()

    def insert(self, peer, action):
        """Insert the action about the peer."""
        self.execute('INSERT INTO %s VALUES(NULL, ?, ?, ?, ?);' % self.NAME,
                     (datetime.now(), peer[0], peer[1], action))
        self.connection.commit()

    def connections(self):
        """:obj:`list` of :obj:`tuple`: Returns all the connection records."""
        self.execute('SELECT * FROM %s;' % self.NAME)
        return [(r[0], datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S.%f'), r[2], r[3], r[4])
                for r in self.cursor.fetchall()]


class AuthenticateDatabase(Database):

    NAME = 'authenticate'
    """:obj:`str`: The name of the table in the database."""

    def __init__(self, database, **kwargs):
        """Database for trusted hostname's that are allowed to connect
        to the Network :class:`~msl.network.manager.Manager`.

        Parameters
        ----------
        database : :obj:`str`
            The path to the database file, or ``':memory:'`` to open a
            connection to a database that resides in RAM instead of on disk.
        """
        super().__init__(database, **kwargs)
        self.execute('CREATE TABLE IF NOT EXISTS %s (hostname TEXT, UNIQUE(hostname));' % self.NAME)
        self.connection.commit()

        if not self.hostnames():
            for hostname in ['localhost', '127.0.0.1', '::1']:
                self.insert(hostname)

    def insert(self, hostname):
        """Insert the hostname (only if it does not already exist in the table)."""
        self.execute('INSERT OR IGNORE INTO %s VALUES(?);' % self.NAME, (hostname,))
        self.connection.commit()

    def delete(self, hostname):
        """Insert the hostname (only if it does not already exist in the table)."""
        self.execute('DELETE FROM %s WHERE hostname = ?;' % self.NAME, (hostname,))
        self.connection.commit()

    def hostnames(self):
        """:obj:`list` of :obj:`str`: Returns all the hostname's."""
        self.execute('SELECT * FROM %s;' % self.NAME)
        return [h[0] for h in self.cursor.fetchall()]


if __name__ == '__main__':

    cd = ConnectionsDatabase(':memory:')
    cd.insert(('localhost', 1234), 'hello')
    cd.insert(('127.0.0.1', 5678), 'world')

    print('Database: ' + cd.path)
    for table in cd.tables():
        print('  Table: ' + table)
        for info in cd.table_info(table):
            print('    column[{}]: {}'.format(info[0], info[1:]))
        for record in cd.connections():
            print('    record:', record)

    ad = AuthenticateDatabase(':memory:')
    ad.insert('127.0.0.1')
    ad.insert('localhost')
    ad.insert('::1')
    ad.insert('localhost')
    ad.insert('127.0.0.1')
    ad.insert('localhost')
    ad.insert('::1')
    ad.insert('0.0.0.0')
    ad.insert('127.0.0.1')

    ad.delete('0.0.0.0')

    print('Database: ' + ad.path)
    for table in ad.tables():
        print('  Table: ' + table)
        for info in ad.table_info(table):
            print('    column[{}]: {}'.format(info[0], info[1:]))
        for name in ad.hostnames():
            print('    hostname:', name)
