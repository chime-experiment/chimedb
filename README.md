# `chimedb.core`—CHIME database core interface package

This package provides low-level routines for accessing the CHIME SQL database.

**NB**: this package doesn't define any tables itself.  In general, to use the
database, you will also need one or more packages which define object-relational
models for the tables in the database.  Packages which define tables include:

* [chimedb.data_index](https://github.com/chime-experiment/chimedb_di): for data
    index tables updated by alpenhorn
* [chimedb.dataflag](https://github.com/chime-experiment/chimedb_dataflag):
    for data flags, and the associated `cdf` CLI
* [chimedb.dataset](https://github.com/chime-experiment/chimedb_dataset):
    for dataset tables updated by comet
* [ch_util](https://bitbucket.org/chime/ch_util): for all other tables

## Connecting to the Database

This package contains no configuration information for connecting to the
database itself.  Most CHIME users will want to install the
[chimedb.config](https://github.com/chime-experiment/chimedb_config) package
to automatically configure their connection.  Other configuration methods
are explained in the `connectdb` documentation.

## Usage

Typically, a connection is created by calling `connect()`:
```
import chimedb.core as db
db.connect()
```

A connecton can be closed with:
```
db.close()
```
All uncommitted transactions will be abandoned.  Explicitly closing the database is not usually required: the database will automatically be closed on exit.

### Diagnostics
You can see which connection the module has made with the database by inspecting the current connector:
```
db.connect()
print(db.connectdb.current_connector().description)
```

## Contents

This package contains:

### Exceptions

The base exception:

* `CHIMEdbError(RuntimeError)`

  The base chimedb exception.  Should never be raised explicitly,
  but all other chimedb exceptions are subclasses, and this can
  be used to catch all chimedb exceptions.

Exceptions related to database connections:

* `ConnectionError(CHIMEdbError)`

   An error occured while trying to establish a connection to the database.

* `NoRouteToDatabase(ConnectionError)`

  No route to the database server could be found.  This is a subclass of the
  more generic ConnectionError exception.

Exceptions related to database operations (queries and updates):

* `AlreadyExistsError(CHIMEdbError)`

  An attempt was made to add a record with a key that already
  exists.

* `InconsitencyError(CHIMEdbError)`

  The database is internally inconsistent.  This shouldn't
  be possible through normal operation.

* `NotFoundError(CHIMEdbError)`

  A query returns no results.

* `ValidationError(CHIMEdbError)`

  A cell value failed validation.

### Functions

* `close()`

  Close all open database connections.

* `connect(read_write=False, reconnect=False)`

  Initialise a connection to the database.  All connections are
  thread-local; they cannot be shared between threads.

  * `read_write : bool`

    If `True`, use a read-write connection to the database, otherwise
    a read-only connection will be established.

  * `reconnect : bool`

    If `True`, re-establish a new connection to the database, even if
    one already exists.

* `test_enable()`

  Turn on test-safe mode.  For use during unit testing.  Turning on test-safe
  mode prevents actually running tests on the production database.  See
  `connectdb` for full details.

### Globals

* `proxy`

  A `peewee.Proxy()` which can be used to access the database.  Initialised by a
  call to `chimedb.connect()`.

### Modules

* `connectdb`

  Very low-level connection implementation.  Most users will want to use the
  `chimedb.connect()` function to connect to the database rather than using this
  module explicitly.

* `orm`

  Helper functions and base table classes used by other packages when defining
  the object-relational models for tables in the database.
