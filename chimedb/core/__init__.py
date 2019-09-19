"""CHIME core database interface package

This package provides low-level routines for accessing the CHIME SQL
database.

Exceptions
==========

The following exceptions are defined:

* `CHIMEdbError(RuntimeError)`
    This is the base chimedb exception.  It should never be raised explicitly,
    but all other chimedb exceptions are subclasses, and this can be used to
    catch all chimedb exceptions.

Exceptions related to database connections:

* `ConnectionError(CHIMEdbError)`
    An error occured while trying to establish a connection to the database.

* `NoRouteToDatabase(ConnectionError)`
    No route to the database server could be found.  This is a subclass of
    the more generic ConnectionError exception.

Exceptions related to database operations (queries and updates):

* `AlreadyExistsError(CHIMEdbError)`
    An attempt was made to add a record with a key that already exists.

* `InconsitencyError(CHIMEdbError)`
    The database is internally inconsistent.  This shouldn't be possible through
    normal operation.

* `NotFoundError(CHIMEdbError)`
    A query returns no results.

* `ValidationError(CHIMEdbError)`
    A cell value failed validation.


Functions
=========

The following functions are provided:

* `connect(read_write=False, reconnect=False)`
    Initialise a connection to the database.

    This function is equivalent to the `chimedb.core.orm.connect_database`
    function.  All connections are thread-local; they cannot be shared between
    threads.

Globals
=======

* `proxy`
    A `peewee.Proxy()` which can be used to access the database.  Initialised by
    a call to `chimedb.core.connect()`.

Modules
=======

* `connectdb`
    Very low-level connection implementation.  Most users will want to use the
    `chimedb.core.connect()` function to connect to the database rather than
    using this module explicitly.

* `orm`
    Helper functions and base table classes used by other packages when defining
    the object-relational models for tables in the database.

* `util`
    Utility functions for database maintenance.

Notes
=====

This package doesn't define any tables itself.  In general, to use
the database, you will also need one or more packages which define
object-relational models for the tables in the database.  Packages
which define tables include:

* `chimedb_di`
        for data index tables updated by alpenhorn
* `ch_util`
        for many other tables

"""
from .exceptions import (
    CHIMEdbError,
    NotFoundError,
    ValidationError,
    InconsistencyError,
    AlreadyExistsError,
    NoRouteToDatabase,
    ConnectionError,
)
from .orm import connect_database as connect
from .orm import database_proxy as proxy
from .connectdb import close

__version__ = "0.2.0"
