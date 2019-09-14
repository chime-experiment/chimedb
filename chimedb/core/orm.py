"""
Base classes for the CHIME ORM.
"""
# === Start Python 2/3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614

# === End Python 2/3 compatibility

import peewee as pw
import ujson
from .exceptions import ConnectionError

# Logging
# =======

# Set default logging handler to avoid "No handlers could be found for logger
# 'layout'" warnings.
import logging

# All peewee-generated logs are logged to this namespace.
logger = logging.getLogger("chimedb")
logger.addHandler(logging.NullHandler())

# Global variables and constants.
# ================================

database_proxy = pw.Proxy()

# Helper classes for the peewee ORM
# =================================


class EnumField(pw.Field):
    """Implements an enum field for the ORM.

    Why doesn't peewee support enums? That's dumb. We should make one."""

    field_type = "enum"

    def __init__(self, enum_list, *args, **kwargs):
        self.enum_list = enum_list
        self.value = []
        for e in enum_list:
            self.value.append("'" + str(e) + "'")
        super(EnumField, self).__init__(*args, **kwargs)

    def clone_base(self, **kwargs):
        return super(EnumField, self).clone_base(enum_list=self.enum_list, **kwargs)

    def get_modifiers(self):
        return self.value or None

    def coerce(self, val):
        return str(val or "")


class JSONDictField(pw.TextField):
    """Fake JSON dict field.

    In theory MySQL has a native JSON field, but peewee does not support it.
    """

    def db_value(self, value):
        """Serialize the python values for storage in the db."""

        if value is None:
            return None

        if not isinstance(value, dict):
            raise ValueError("Python value must be a dict. Received %s" % type(value))

        return ujson.dumps(value)

    def python_value(self, value):
        """Deserialize the DB string to JSON."""

        if value is None:
            return None

        pyval = ujson.loads(value)

        if not isinstance(pyval, dict):
            raise ValueError(
                "Database value must convert to dict. Got %s" % type(pyval)
            )

        return pyval


class base_model(pw.Model):
    """Base class for all table models."""

    class Meta(object):
        database = database_proxy


class name_table(base_model):
    """Base class for all models with a "name" field.

    This class allows for caching of frequent queries: use the :meth:`from_id`
    and :meth:`from_name` methods. They will only query the database the first
    time that a given row is requested, and then use a cached value.

    Methods
    -------
    clear_cache
    get_query_cache
    get_name
    get_id
    fill_cache
    """

    # Class variable holding the query cache
    _query_cache = dict()

    @classmethod
    def clear_cache(cls):
        """Clear any cached look-ups for this table."""
        cls._query_cache[cls.__name__] = dict()

    @classmethod
    def get_query_cache(cls, field, val):
        """Get and cache a row of the table where the value of column `field`
        equals `val`.

        The database is only queried once for a given `field`, `val` pair.
        Subsequent calls use the cached value.

        Parameters
        ----------
        field : string
            The name column to match
        val : string
            The value of the column to match

        Returns
        -------
        row : :obj:`name_table`
            A row of the table.
        """
        if val is None:
            return None

        class_cache = cls._query_cache.setdefault(cls.__name__, dict())
        column_cache = class_cache.setdefault(field, dict())

        if val not in column_cache:
            column_cache[val] = cls.get(**{field: val})

        return column_cache[val]

    @classmethod
    def from_name(cls, name):
        """Get a row of the table using the "name" column.

        The DB is only queried once for a given **name**. Subsequent calls use a
        cached value.

        Equivalent to `get_query_cache("name", name)`.

        Parameters
        ----------
        name : string
          The value of the **name** column to look for.

        Returns
        -------
        row : :obj:`name_table`
          A row of the table.
        """
        return cls.get_query_cache("name", name)

    @classmethod
    def from_id(cls, id):
        """Get a row of the table using the ID column.

        The DB is only queried once for a given **id**. Subsequent calls use a
        cached value.

        Equivalent to `get_query_cache("id", id)`.

        Parameters
        ----------
        id : integer
          The value of the **id** column to look for.

        Returns
        -------
        row : :obj:`name_table`
          A row of the table.
        """
        return cls.get_query_cache("id", id)

    @classmethod
    def fill_cache(cls):
        """Cache the values of the "name" and "id" columns for all rows for this
        table.

        The DB is only queried the first time this is called. If the cache is
        already full, this method does nothing.
        """

        class_cache = cls._query_cache.setdefault(cls.__name__, dict())

        if "__fill_cache__" not in class_cache:
            name_cache = class_cache.setdefault("name", dict())
            id_cache = class_cache.setdefault("id", dict())

            for row in cls.select():
                id_cache[row.id] = row
                name_cache[row.name] = row

            class_cache["__fill_cache__"] = True


# Initializing connection to database.
# ====================================


def connect_database(read_write=False, reconnect=False):
    """Initialize the connection to the CHIME database.

    If a basic connection to the database has already been established
    through a call to `connectdb.connect`, the database connector
    already established by that call will be used to connect.

    Otherwise, `connectdb.connect` will be called by this function to
    establish the connection.

    This function must be called again if you use `connectdb` to change
    the connection method after importing this module.

    A call to this function must be made before using the `chimedb` proxy
    object (`chimedb.core.proxy`, AKA `chimedb.core.orm.database_proxy`).

    Parameters
    ----------
    `read_write` : bool
        If True, use a read-write connection to the database, otherwise
        a read-only connection will be established.
    `reconnect` : bool
        Force a reconnection.

    Raises
    ------
    `chimedb.ConnectionError`
        If a database connection could not be established.

    """

    from . import connectdb

    connectdb.connect()

    # Don't attempt to connect if the DB connection doesn't exist (due
    # to MPI reasons).
    if not connectdb.connect_this_rank():
        return

    # Check if we have already connected the database proxy and only continue if
    # we are set to reconnect
    if not reconnect and database_proxy.obj is not None:
        return

    # Retrieve the database connection
    connector = connectdb.current_connector(read_write)

    if not connector:
        raise ConnectionError("No database connection could be established.")

    pw_database = connector.get_peewee_database()
    database_proxy.initialize(pw_database)


def create_tables(packages=None):
    """Create tables in chimedb.

    Parameters
    ----------
    packages : list, optional
        List of chimedb subpackages to create tables from.
    """

    import importlib
    import chimedb

    # Ensure we have a list
    if isinstance(packages, str):
        packages = [packages]

    # If packages was not set, try and get all subpackages of chimedb
    if packages is None:
        import pkgutil

        # Get a list of all subpackages
        packages = [
            info.name + ".orm"
            for info in pkgutil.iter_modules(chimedb.__path__, chimedb.__name__ + ".")
        ]

    # Import all the specified packages to get them to get their subclasses regiseted
    for pkgname in packages:
        try:
            importlib.import_module(pkgname)
        except ModuleNotFoundError:
            pass

    # Construct the list of tables
    tables = []
    for cls in base_model.__subclasses__():

        # Skip the name_table as it's not really a table
        if cls is name_table:
            continue
        tables.append(cls)

    logger.info("Creating tables: %s", ", ".join([table.__name__ for table in tables]))
    database_proxy.create_tables(tables)
