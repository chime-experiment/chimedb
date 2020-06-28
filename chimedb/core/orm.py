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
    """Implements an ENUM field for peewee.

    Only MySQL and PostgreSQL support `ENUM` types natively in the database. For
    Sqlite (and others), the `ENUM` is implemented as an appropriately sized
    `VARCHAR` and the validation is done at the Python level.

    .. warning::
        For the *native* ``ENUM`` to work you *must* register it with peewee by
        doing something like::

            db.register_fields({'enum': 'enum'})

        This will happen automatically if you use chimedb.core.connect() to
        create the database connection.

    Parameters
    ----------
    enum_list : list
        A list of the string values for the ENUM.

    Attributes
    ----------
    native : bool
        Attempt to use the native database `ENUM` type. Should be set at the
        *class* level. Only supported for MySQL or PostgreSQL, and will throw
        SQL syntax errors if used for other databases.
    """

    native = True

    @property
    def field_type(self):
        if self.native:
            return "enum"
        else:
            return "string"

    def __init__(self, enum_list, *args, **kwargs):
        self.enum_list = enum_list

        self.value = []
        for e in enum_list:
            self.value.append("'%s'" % e)

        self.maxlen = max([len(val) for val in self.enum_list])

        super(EnumField, self).__init__(*args, **kwargs)

    def clone_base(self, **kwargs):
        # Add the extra parameter so the field is cloned properly
        return super(EnumField, self).clone_base(enum_list=self.enum_list, **kwargs)

    def get_modifiers(self):
        # This routine seems to be for setting the arguments for creating the
        # column.
        if self.native:
            return self.value or None
        else:
            return [self.maxlen]

    def coerce(self, val):
        # Coerce the db/python value to the correct output. Also perform
        # validation for non native ENUMs.
        if self.native or val in self.enum_list:
            return str(val or "")
        else:
            raise TypeError("Value %s not in ENUM(%s)" % str(self.value))


class JSONDictField(pw.TextField):
    """Fake JSON dict field.

    In theory MySQL has a native JSON field, but peewee does not support it.
    """

    field_type = "LONGTEXT"

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
    This includes _any_ use of a base_model-derived table class to access
    data.

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

    connectdb.connect(reconnect)

    # Don't attempt to connect if the DB connection doesn't exist (due
    # to MPI reasons).
    if not connectdb.connect_this_rank():
        return

    # Retrieve the database connection
    connector = connectdb.current_connector(read_write)

    if not connector:
        raise ConnectionError("No database connection could be established.")

    pw_database = connector.get_peewee_database()

    # Set up and register EnumField
    global EnumField

    if isinstance(pw_database, (pw.MySQLDatabase, pw.PostgresqlDatabase)):
        pw_database.field_types["enum"] = "enum"
        EnumField.native = True
    else:
        EnumField.native = False

    # Initialise the proxy
    database_proxy.initialize(pw_database)


def create_tables(packages=None, ignore=list(), check=False):
    """Create tables in chimedb.

    Parameters
    ----------
    packages : list, optional
        List of chimedb subpackages to create tables from.
    ignore : list, optional
        List of tables to skip creating
    check : bool, optional
        If True, instead of creating tables, just
        list tables which would be created
    """

    import importlib

    # Ensure we have a read-write connection
    if not check:
        connect_database(read_write=True)

    # Ensure we have a list
    if isinstance(packages, str):
        packages = [packages]

    # The ignore table could be string class names or else actual classes
    ignore = [item if isinstance(item, str) else item.__name__ for item in ignore]

    # Add abstract table classes that should always be ignored.
    ignore.append("name_table")

    # If packages was not set, try and get all subpackages of chimedb
    if packages is None:
        import pkgutil
        import chimedb

        # These subpackages we never import
        blacklist = ["chimedb.setup", "chimedb.core", "chimedb.config"]

        # Get a list of all subpackages
        packages = [
            info.name + ".orm"
            for info in pkgutil.iter_modules(chimedb.__path__, chimedb.__name__ + ".")
            if info.name not in blacklist
        ]

    # Import all the specified packages to get them to get their subclasses regiseted
    for pkgname in packages:
        try:
            importlib.import_module(pkgname)
        except ModuleNotFoundError:
            pass

    # Construct the list of tables
    def find_tables(model, tables, ignore):
        for cls in model.__subclasses__():

            if cls.__name__ in ignore:
                continue
            tables.append(cls)

            # Look for subclasses recursively
            find_tables(cls, tables, ignore)

    tables = []
    find_tables(base_model, tables, ignore)

    if check:
        tables_by_module = dict()

        for table in tables:
            modlist = tables_by_module.setdefault(table.__module__, list())
            modlist.append(table.__name__)

        logger.info("Would create:")
        for mod in sorted(tables_by_module.keys()):
            logger.info("    from {0}:".format(mod))
            for table in sorted(tables_by_module[mod]):
                logger.info("        " + table)
    else:
        logger.info(
            "Creating tables: %s", ", ".join([table.__name__ for table in tables])
        )
        database_proxy.create_tables(tables)
