"""
Save the information about each connection to the network manager in a database.
"""
import os
import sqlite3
import logging


log = logging.getLogger(__name__)


class Database(object):

    NULL = 'NULL'
    INTEGER = 'INTEGER'
    REAL = 'REAL'
    TEXT = 'TEXT'
    BLOB = 'BLOB'

    # a list of data types that are allowed for a column in a database table
    _VALID_DATA_TYPES = ['NULL', 'INTEGER', 'REAL', 'TEXT', 'BLOB']

    def __init__(self, database, **kwargs):
        """Connect to a SQLite database.

        Creates the database if does not already exist.

        Parameters
        ----------
        database : :obj:`str`
            The path to the database file, or ``':memory:'`` to open a connection to a
            database that resides in RAM instead of on disk.

        Example
        -------
        >>> from msl.network import Database
        >>> db = Database(':memory:')
        >>> db.create_table('devices', [['manufacturer', db.TEXT], ['model', db.TEXT], ['serial', db.TEXT]])
        >>> db.create_table('users', [['name', db.TEXT], ['age', db.INTEGER, 15], ['height', db.REAL]])
        >>> db.table_names()
        ['devices', 'users']
        >>> db.write('INSERT INTO users VALUES(NULL, "Sara", 33, 1.59)')  # NULL is required to auto-increment the primary id
        >>> db.write('INSERT INTO users VALUES(NULL, ?, ?, ?)', ('Bob', 27, 1.73))
        >>> db.write('INSERT INTO users(name, age, height) VALUES("Lee", 18, 1.65)')  # if you specify the column names then you can ignore the NULL
        >>> db.write('INSERT INTO users(name, age, height) VALUES(?, ?, ?)', ('Buddy', 43, 1.88))
        >>> db.write('INSERT INTO users(name) VALUES(?)', ('Unknown',))  # only specify a value for 'name' so that 'age' and 'height' will get their default value
        >>> db.column_names('devices')
        ['pid', 'manufacturer', 'model', 'serial']
        >>> db.column_datatypes('devices')
        ['INTEGER', 'TEXT', 'TEXT', 'TEXT']
        >>> db.column_names('users')
        ['pid', 'name', 'age', 'height']
        >>> db.column_datatypes('users')
        ['INTEGER', 'TEXT', 'INTEGER', 'REAL']
        >>> for column in db.table_info('users'):
        ...     print(tuple(column))
        (0, 'pid', 'INTEGER', 0, None, 1)
        (1, 'name', 'TEXT', 0, None, 0)
        (2, 'age', 'INTEGER', 0, '15', 0)
        (3, 'height', 'REAL', 0, None, 0)
        >>> for row in db.read('SELECT * FROM users'):
        ...     print(tuple(row))
        (1, 'Sara', 33, 1.59)
        (2, 'Bob', 27, 1.73)
        (3, 'Lee', 18, 1.65)
        (4, 'Buddy', 43, 1.88)
        (5, 'Unknown', 15, None)
        """
        self._path = database
        self._connection = None

        # open the connection to the database
        if database == ':memory:':
            log.debug('creating a database in RAM')
        elif not os.path.isfile(database):
            log.debug('creating a new database: ' + database)
        else:
            log.debug('opening: ' + database)
        self._connection = sqlite3.connect(database, **kwargs)
        self._connection.row_factory = sqlite3.Row
        self._cursor = self._connection.cursor()

    @property
    def path(self):
        """:obj:`str`: The path of the database file."""
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
           The connection to the database is automatically closed when the :class:`Database`
           object gets destroyed.
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            log.debug('closed: ' + self.path)

    def create_table(self, name, columns):
        """Create a new table in the database.

        Only creates a table if a table with this name does not already exist in
        the database. If a table with this name already exists then this function
        does not modify the database.

        The first column of the table is an ``INTEGER PRIMARY KEY AUTOINCREMENT``.

        Parameters
        ----------
        name : :obj:`str`
            The name of the table.
        columns : :obj:`list`
            A list of [ [``name``, ``datatype``, ``default``], ... ] values, where
            ``name`` is the name of the database column, ``datatype`` is the datatype
            of the column -- it must be one of **NULL**, **INTEGER**, **REAL**, **TEXT**
            or **BLOB** -- and ``default`` is an optional argument which can be specified
            to use as the default value for this column if no value is specified when
            inserting a record into the database.

        Raises
        ------
        ValueError
            If a ``datatype`` value is is invalid.

        Examples
        --------
        >>> db = Database(':memory:')
        >>> db.create_table('users', [['name', db.TEXT], ['age', db.INTEGER, 15], ['height', db.REAL]])
        """
        command = 'CREATE TABLE IF NOT EXISTS %s (pid INTEGER PRIMARY KEY AUTOINCREMENT, ' % name.replace(' ', '_')
        for row in columns:
            if len(row) < 2:
                raise ValueError('Must specify the name and the datatype of each column')
            typ = row[1].upper()
            if typ not in self._VALID_DATA_TYPES:
                raise ValueError('Invalid datatype {}. Must be one of {}'.format(typ, ', '.join(self._VALID_DATA_TYPES)))
            if len(row) == 2:
                command += '{} {}, '.format(row[0], typ)
            else:
                command += '{} {} DEFAULT {}, '.format(row[0], typ, row[2])
        self.write(command[:-2] + ')')

    def read(self, command, conditions=None):
        """Execute a SQL command to read values from the database.

        Parameters
        ----------
        command : :obj:`str`
            The SQL command to send to the database.
        conditions : :obj:`list` or :obj:`tuple`, optional
            The conditions of the values to read from the database.

            .. note::
               You should not assemble your query using Python’s string operations
               because doing so is insecure_. Instead, use the DB-API’s parameter
               substitution where a ``?`` is used as a placeholder where ever you
               want to use a value.

               # Never do this -- insecure!

               ``read("SELECT * FROM stocks WHERE symbol='%s'" % 'NZD')``

               # Do this instead

               ``read('SELECT * FROM stocks WHERE symbol=?', ('NZD',))``

            If `values` is :obj:`None` then this function only sends the value of
            `command` to the database.

            .. _insecure: https://docs.python.org/3/library/sqlite3.html

        Returns
        -------
        :obj:`list` of :class:`sqlite3.Row`
            The requested data from the database.
        """
        try:

            if conditions is None:
                log.debug(command)
                self._cursor.execute(command)
            else:
                log.debug(command + ' -- ' + '{!r}'.format(conditions))
                self._cursor.execute(command, conditions)
            values = self._cursor.fetchall()
        except Exception as e:
            log.error(e)
            raise
        return values

    def write(self, command, values=None):
        """Execute the SQL command to write data to the database.

        Parameters
        ----------
        command : :obj:`str`
            The SQL command to send to the database.
        values : :obj:`list` or :obj:`tuple`, optional
            The values to write to the database.

            .. note::
               You should not assemble your query using Python’s string operations
               because doing so is insecure_. Instead, use the DB-API’s parameter
               substitution where a ``?`` is used as a placeholder where ever you
               want to use a value.

               # Never do this -- insecure!

               ``write("INSERT INTO people VALUES ('%s', %d)" % ('John', 32))``

               # Do this instead

               ``write("INSERT INTO people VALUES (?, ?)", ('John', 32))``

            .. _insecure: https://docs.python.org/3/library/sqlite3.html

            If `values` is :obj:`None` then this function only sends the value of
            `command` to the database.
        """
        try:
            if values is None:
                log.debug(command)
                self._cursor.execute(command)
            else:
                log.debug(command + ' -- ' + '{!r}'.format(values))
                self._cursor.execute(command, values)
                self._connection.commit()
        except Exception as e:
            log.error(e)
            raise

    def table_names(self):
        """:obj:`list` of :obj:`str`: A list of the table names that are in the database."""
        tables = self.read("SELECT name FROM sqlite_master WHERE type='table'")
        return [t[0] for t in tables if t[0] != 'sqlite_sequence']

    def table_info(self, name):
        """Returns the information about each column in the table.

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

        Example
        -------
        >>> from msl.network import Database
        >>> db = Database(':memory:')
        >>> db.create_table('users', [['name', db.TEXT], ['age', db.INTEGER, 15], ['height', db.REAL]])
        >>> info = db.table_info('users')
        >>> tuple(info[0])
        (0, 'pid', 'INTEGER', 0, None, 1)
        >>> tuple(info[1])
        (1, 'name', 'TEXT', 0, None, 0)
        >>> tuple(info[2])
        (2, 'age', 'INTEGER', 0, '15', 0)
        >>> info[0].keys()
        ['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk']
        >>> info[0]['pk']
        1
        >>> info[2]['dflt_value']
        '15'
        """
        return self.read("PRAGMA table_info('%s');" % name)

    def column_names(self, table_name):
        """Returns the names of the columns in a table.

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
        """Returns the datatype of each column in a table.

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
