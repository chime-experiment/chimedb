"""
==========================================================================
Connection handler for the CHIME database (:mod:`~chimedb.core.connectdb`)
==========================================================================

.. currentmodule:: chimedb.core.connectdb

Upon a call to `connect`, initialise connections to the CHIME database. These
can be accessed using the `current_connector()` function.  Connections are not
shared between threads.

.. warning::
    Do not call `connect` during an import statement. This will cause the
    process to hang as the ssh tunnel attempts to create threads which can't
    acquire the global import lock.

This module needs configuration data for the database connection.  Several
different configuration sources are probed for, in order.  The first source
that exists is used, even if the connection configuration supplied by that
source doesn't result in a successful connection to the database.

The configuration sources searched for are:

    * an environment variable CHIMEDB_SQLITE, containing the path to a
        sqlite database or a sqlite URI
    * a YAML file specified by the environment variable CHIMEDBRC
    * a YAML file called ``.chimedbrc`` in the current directory
    * a YAML file called ``.chimedbrc`` in the user's home directory
    * a YAML file located at ``/etc/chime/chimedbrc``
    * a Python module called `chimedb.config`.

If none of these configuration sources can be found, NoRouteToDatabase is
raised and the connection attempt fails.

Any of the YAML files listed above, if present, should look like:

.. code-block:: yaml

    chimedb:
        db_type:         mysql
        db:              <database name>
        user_ro:         <read-only username>
        passwd_ro:       <read-only password>
        user_rw:         <read-write username>
        passwd_rw:       <read-write password>
        host:            <database hostname>
        port:            <database port number, default 3306>
        tunnel_host:     <connection tunnel hostname>
        tunnel_user:     <connection tunnel username>
        tunnel_identity: <connection tunnel identify file>

Or for a sqlite database:

.. code-block:: yaml

    chimedb:
        db_type:         sqlite
        db:              <filename or URI>

(Of course, you should put proper arguments in your file! No quotation marks
should be used for strings.) If no tunnel is required, simply omit the
``tunnel_`` entries.  The password entries can also be omitted if a password
is not needed.

If none of the YAML files are found, the last thing tried is to import a
Python module called ``chimedb.config``.  This module, if present, should
provide two lists (or other iterable object) called
``chimedb.config.connectors`` and ``chimedb.config.connectors_rw``.  These
two objects should contain BaseConnector-derived objects containing the
connector data.  For both the lists (or iterables), the connectors are
tried in order until one succeeds.

Classes
=======

.. autosummary::
    :toctree: generated/

    BaseConnector
    MySQLConnector
    SqliteConnector


Attributes
==========

These attributes tell the module how to connect to the CHIME database.

:const:`ALL_RANKS`
    Whether to try to connect all ranks in an MPI job, or just rank=0.
    Default: False


Test-Safe Mode
==============

To safely use this package without accidentally running tests against
the production database, you can set the environment variable
`CHIMEDB_TEST_ENABLE` to a non-empty value or call `chimedb.core.test_enable()`
before calling `connect()`.

Test mode disables all the standard configuration sources:

    * Environmental variables CHIMEDB_SQLITE and CHIMEDBRC are ignored
    * None of the default RC file locations are checked
    * No attempt is made to use the `chimedb.config` module

Instead the following test-only configuration sources are used, in order:

    * The environment variable CHIMEDB_TEST_SQLITE
    * The environment variable CHIMEDB_TEST_RC

These work the same as CHIMEDB_SQLITE and CHIMEDBRC, except that a value
for CHIMEDB_TEST_RC that contains the string "chimedbrc" will be rejected,
to further ensure deployment configuration is not used.

If neither environment variable is present, attempting to connect to the
database will result in an empty in-memory sqlite database being created
and connected to.  This in-memory database will exist until close() is
called (or the program exits).
"""

import os
import logging
import mysql.connector
import peewee as pw
from playhouse.mysql_ext import MySQLConnectorDatabase

import socket
import sqlite3
import yaml
import sshtunnel
import threading

from .exceptions import NoRouteToDatabase, ConnectionError


# Globals
# =======

# Set module logger.
_logger = logging.getLogger("chimedb")

# Thread-local connectors: the MySQLdb module prohibits
# multiple threads from using the same database connection
# so we store the current connection in thread-local storage
# NOTE: we have switched to the pure python mysql.connector package, but I've left this
# in place for now for safety
_threadlocal = threading.local()

# This cannot be "localhost" because that is used as a special
# value by MySQL to indicate that it should connect to a local
# socket
_LOCALHOST = "127.0.0.1"

# We check these in order before trying chimedb.config
_RC_FILES = [
    os.path.join(os.curdir, ".chimedbrc"),
    os.path.join(os.path.expanduser("~"), ".chimedbrc"),
    "/etc/chime/chimedbrc",
]

# Cluster config
# =============
#
# Allow all ranks to connect to the DB
ALL_RANKS = False


# Test-safe mode
_TEST_ENABLE = False


def test_enable():
    """Enable test-safe mode."""
    global _TEST_ENABLE
    if not _TEST_ENABLE:
        _logger.debug("Enabling test-safe mode")
        _TEST_ENABLE = True


# Log filtering of mysql.connector
# ================================
# mysql.connector outputs the MySQL password to the log at log-level DEBUG.
# By default, we filter these messages out, but that can be disabled at runtime
# by calling ``connectdb.secure_logging(False)``


class PasswordFilter(logging.Filter):
    def filter(self, record):
        """Drops password messages from the log."""
        return "password: %s" not in record.msg


mclog = logging.getLogger("mysql.connector.connection")

_password_filter = PasswordFilter()

# By default, the mysql.connector is filtered
mclog.addFilter(_password_filter)

_mysql_connector_log_filtered = True  # True if the filter is installed


def secure_logging(enable=True):
    """Enable or disable the mysql.connector log filter."""
    global _mysql_connector_log_filtered, _password_filter

    if enable and not _mysql_connector_log_filtered:
        # Start filtering
        mclog.addFilter(_password_filter)
        _mysql_connector_log_filtered = True
    elif not enable and _mysql_connector_log_filtered:
        # Stop filtering
        mclog.removeFilter(_password_filter)
        _mysql_connector_log_filtered = False


def current_connector(read_write=False):
    """The current database connector for this thread, or None if no
    database connection has been made.

    Parameters
    ----------
    read_write : bool, optional
        If True, the read-write connector is returned.  If False, or
        omitted, the read-only connector to the database is returned.

    Returns
    -------
    BaseConnector-derived object or None
    """
    if read_write:
        return getattr(_threadlocal, "current_connector_RW", None)
    return getattr(_threadlocal, "current_connector", None)


def connect_this_rank():
    """Returns True if we should attempt a connection to the database
    from the current MPI rank (or if no MPI support is present).
    """
    if ALL_RANKS:
        return True

    try:
        from mpi4py import MPI

        return MPI.COMM_WORLD.Get_rank() == 0
    except ImportError:
        return True


# Database Class
# ==============


class RetryOperationalError(object):
    """Rewrite of the former `peewee.shortcuts.RetryOperationalError` mixin.

    Source: https://github.com/coleifer/peewee/issues/1472
    """

    def execute_sql(self, sql, params=None, commit=None):
        """Extend default execute_sql to retry.

        Retries once on pw.OperationalError, but only if not
        in a transaction, and only if the database is set to
        autoreconnect.
        """
        try:
            cursor = super().execute_sql(sql, params, commit)
        except pw.OperationalError:
            # If we're in a transaction or the database isn't
            # set to autoconnect, there's not much we can do,
            # so just continue to crash
            if not self.autoconnect or self.in_transaction():
                raise

            # Close the broken connector, if it's still open
            if not self.is_closed():
                self.close()

            # And then retry.  This will re-open the DB because
            # we've just closed it and autoconnect is True.
            cursor = super().execute_sql(sql, params, commit)
        return cursor


class MySQLDatabaseReconnect(RetryOperationalError, MySQLConnectorDatabase):
    """A MySQL database class which will automatically retry connections."""

    pass


# Connectors
# ==========


class BaseConnector(object):
    """Abstract base class for all data base connectors.

    A connector is an object that knows how to create various types of
    connections to a given database.

    Initialization signature is subclass dependant.  Subclasses must
    re-implement get_connection and get_peewee_database.

    Attributes
    ----------
    description

    Static methods
    --------------
    from_dict

    Methods
    -------
    get_connection
    get_peewee_database

    """

    def get_connection(self):
        """Get a standard connection to the database."""
        raise NotImplementedError("BaseConnector must be subclassed.")

    def get_peewee_database(self):
        """Get :mod:`peewee` database object."""
        raise NotImplementedError("BaseConnector must be subclassed.")

    @property
    def description(self):
        """A human-readable description of this connector as a string."""
        return "Unspecified connection"

    @staticmethod
    def from_dict(d, context=None):
        """Returns a three-element tuple containing:
            * a single-item list containing a subclass of :class:`BaseConnector` for a read-only connection
            * a single-item list containing a subclass of :class:`BaseConnector` for a read-write connection
            * the passed-in context
        based on data in a dictionary.

        Typically invoked to initialise a connector from a parsed YAML file.
        """

        defaults = {
            "passwd_ro": "",
            "passwd_rw": "",
            "port": "3306",
            "tunnel_host": None,
            "tunnel_user": None,
            "tunnel_identity": None,
        }

        # Default database type is MySQL.
        if "db_type" not in d:
            d["db_type"] = "MySQL"
        if d["db_type"].lower() == "sqlite":
            return (
                [SqliteConnector(d["db"], read_write=False)],
                [SqliteConnector(d["db"])],
                context,
            )
        elif d["db_type"].lower() == "mysql":
            for var, default in defaults.items():
                if var not in d:
                    d[var] = default

            if d["tunnel_identity"]:
                d["tunnel_identity"] == os.path.expanduser(d["tunnel_identity"])

            return (
                [
                    MySQLConnector(
                        d["db"],
                        d["user_ro"],
                        d["passwd_ro"],
                        d["host"],
                        int(d["port"]),
                        d["tunnel_host"],
                        d["tunnel_user"],
                        d["tunnel_identity"],
                    )
                ],
                [
                    MySQLConnector(
                        d["db"],
                        d["user_rw"],
                        d["passwd_rw"],
                        d["host"],
                        int(d["port"]),
                        d["tunnel_host"],
                        d["tunnel_user"],
                        d["tunnel_identity"],
                    )
                ],
                context,
            )
        else:
            ctx = " in {0}".format(context) if context else ""
            raise ValueError("Invalid database type ({0})".format(d["db_type"]) + ctx)


class MySQLConnector(BaseConnector):
    """Connector for MySQL databases.

    Parameters
    ----------
    db : str
        Name of the database on the server.
    user : str
        MySQL user name
    passwd : str
        MySQL password
    host : str
        MySQL server hostname.
    port : int
        TCP port of MySQL server. Default: standard port (3306).
    tunnel_host : str
        Hostname to tunnel through to connect to MySQL server using ssh port
        forwarding. Default is to not tunnel but connect directly.
    tunnel_user : str
        User name to use to log into tunnel server.
    identity_file : str
        Filename of ssh private key to use to log into tunnel server.
    """

    _tunnel = None

    def __init__(
        self,
        db,
        user,
        passwd,
        host,
        port,
        tunnel_host=None,
        tunnel_user=None,
        tunnel_identity=None,
    ):
        self._database = None

        self._db = db
        self._user = user
        self._passwd = passwd
        self._host = host
        self._port = port
        self._tunnel_host = tunnel_host
        self._tunnel_port = None
        self._tunnel_user = tunnel_user
        self._tunnel_identity = tunnel_identity

    def get_connection(self):
        self.ensure_route_to_database()
        host, port = self._host_port()

        # See if a chimedb timeout variable has been set correctly
        timeout = 1

        if _have_envvar("CHIMEDB_CONNECT_TIMEOUT"):
            os_timeout = os.environ["CHIMEDB_CONNECT_TIMEOUT"]
            # Ensure that this is an integer
            if os_timeout.isdigit():
                timeout = int(os_timeout)
            else:
                _logger.warning(
                    f"CHIMEDB_CONNECT_TIMEOUT set to an invalid value: {os_timeout}"
                )

        try:
            connection = mysql.connector.connect(
                db=self._db,
                host=host,
                port=port,
                user=self._user,
                passwd=self._passwd,
                connect_timeout=timeout,
                get_warnings=True,
                use_pure=True,
            )
        except mysql.connector.errors.OperationalError as e:
            if self._tunnel is not None and self._tunnel.is_active:
                self._tunnel.stop(force=True)
            raise ConnectionError(
                "Operational Error while connecting to database: {0}".format(e)
            ) from e
        return connection

    def get_peewee_database(self):
        # This will set self._database to None if a new tunnel is established
        # (possibly because the old one died)
        self.ensure_route_to_database()

        if self._database is None or not self._database.is_connection_usable():
            host, port = self._host_port()
            try:
                self._database = MySQLDatabaseReconnect(
                    self._db,
                    host=host,
                    port=port,
                    user=self._user,
                    passwd=self._passwd,
                    use_pure=True,
                )
            except None:
                # TODO More descriptive here.
                raise ConnectionError("Failed to connect to database.")
        return self._database

    @property
    def description(self):
        out = "MySQL database at %s port %d" % (self._host, self._port)
        if self._tunnel_host:
            out += " tunnelled through {0} to localhost".format(self._tunnel_host)
            if self._tunnel_port is not None:
                out += " port {0}".format(self._tunnel_port)
        return out

    def _host_port(self):
        if self._tunnel_host:
            host = _LOCALHOST
            port = self._tunnel_port
        else:
            host = self._host
            port = self._port
        return host, port

    def ensure_route_to_database(self):
        # Check if we need a tunnel and create one if need be.
        if not self._tunnel_host or tunnel_active(self._tunnel_port):
            return

        if not connect_this_rank():
            return

        # Abandon an existing database connection: if the tunnel isn't
        # active, presumably the connection isn't working
        self._database = None

        _logger.debug(
            "Attempting SSH tunnel to {0}:{1} through {2}".format(
                self._host, self._port, self._tunnel_host
            )
        )

        try:
            self._tunnel = sshtunnel.SSHTunnelForwarder(
                self._tunnel_host,
                ssh_config_file=None,
                remote_bind_address=(self._host, self._port),
                local_bind_address=(_LOCALHOST,),
                ssh_username=self._tunnel_user,
                ssh_pkey=self._tunnel_identity,
            )
        except ValueError:
            msg = "No authentication option for %s" % self._tunnel_host
            raise NoRouteToDatabase(msg)

        # Try to start and handle any exceptions
        try:
            self._tunnel.start()
        except (
            sshtunnel.BaseSSHTunnelForwarderError,
            sshtunnel.HandlerSSHTunnelForwarderError,
        ):
            msg = "Could not tunnel through {0}.".format(self._tunnel_host)
            raise NoRouteToDatabase(msg)

        # Get the bound port number
        self._tunnel_port = self._tunnel.local_bind_address[1]

        # Wait for the tunnel to be established
        self._tunnel.skip_tunnel_checkup = False
        self._tunnel.check_tunnels()  # This waits for the tunnel to come up
        if not self._tunnel.tunnel_is_up[(_LOCALHOST, self._tunnel_port)]:
            raise ConnectionError("An error occurred while setting up the tunnel.")

    def close(self):
        """Close an open connection."""
        if self._database is not None and not self._database.is_closed():
            _logger.debug("Closing database.")
            self._database.close()
            self._database = None
        if self._tunnel is not None and self._tunnel.is_active:
            _logger.debug("Stopping tunnel.")
            self._tunnel.stop(force=True)
            self._tunnel = None


class SqliteConnector(BaseConnector):
    """Connector for Sqlite databases.

    Parameters
    ----------
    db : str
        Filename or URI for the Sqlite database.
    read_write : bool, optional
        If False, make a read-only connector.  Ignored if db is a URI.
        Default: True
    """

    def __init__(self, db, read_write=True):
        # If we've already been handed a URI, we just roll with it
        if not read_write and not db.startswith("file:"):
            self._db = "file:" + db + "?mode=ro"
        else:
            self._db = db

        self._database = None

    def get_connection(self):
        try:
            connection = sqlite3.connect(
                self._db,
                uri=True if self._db.startswith("file:") else False,
            )
        except sqlite3.OperationalError:
            raise ConnectionError(
                "Failed to connect to Sqlite database {0}.".format(self._db)
            )
        return connection

    def get_peewee_database(self):
        if self._database is None or not self._database.is_connection_usable():
            self._database = pw.SqliteDatabase(
                self._db,
                uri=True if self._db.startswith("file:") else False,
            )
        return self._database

    def close(self):
        """Close an open connection."""
        if self._database is not None:
            _logger.debug("Closing database.")
            self._database.close()
            self._database = None

    @property
    def description(self):
        out = "Sqlite database at " + self._db
        return out


# Functions for connecting to the DB.
# ===================================


def tunnel_active(tunnel_port):
    """Returns true if a connection to local port <tunnel_port> succeeds"""
    if tunnel_port is None:
        return False

    sd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Just added this to speed things up.  I think this is enough time. -KM
    sd.settimeout(0.5)
    try:
        # Connect to the given tunnel_port on localhost.
        sd.connect((_LOCALHOST, tunnel_port))
    except socket.error:
        return False
    sd.close()
    return True


def create_tunnel(*args, **kwargs):
    raise NotImplementedError("Try using sshtunnel instead.")


def connected_mysql(db):
    try:
        db.ping()
        return True
    except mysql.connector.errors.InterfaceError:
        return False


def close_mysql(db):
    if connected_mysql(db):
        db.commit()
        db.close()


def _initialize_connections(connectors_to_try, context, rw=False):
    for connector in connectors_to_try:
        try:
            c = connector.get_connection()
            c.close()
        except (
            NoRouteToDatabase,
            ConnectionError,
            mysql.connector.errors.Error,
        ) as err:
            _logger.debug(
                "Unable to connect to {0} defined by {1}: {2}".format(
                    connector.description, context, err
                )
            )
            continue
        if rw:
            msg_conn = "Read-write"
            _threadlocal.current_connector_RW = connector
        else:
            msg_conn = "Read-only"
            _threadlocal.current_connector = connector
        _logger.info(
            "{0} connection to {1} defined by {2} established.".format(
                msg_conn, connector.description, context
            )
        )
        break
    else:
        _logger.warning("Could not establish connection to CHIME database.")


def _have_envvar(name):
    """Returns True if the environment variable `name` is defined and not the
    empty value, otherwise False"""
    if name in os.environ and os.environ[name]:
        return True
    return False


def _try_rc_files():
    global _RC_FILES
    conn = dict()
    section = "chimedb"

    # Try the contents of CHIMEDBRC first, if given
    if _TEST_ENABLE:
        if _have_envvar("CHIMEDB_TEST_RC"):
            _RC_FILES = [os.environ["CHIMEDB_TEST_RC"]]
            if "chimedbrc" in _RC_FILES[0]:
                # OSError is apparently the heir to EnvironmentError
                raise OSError(
                    'Bad value for CHIMEDB_TEST_RC: cannot contain "chimedbrc"'
                )
        else:
            _RC_FILES = []
    else:
        if _have_envvar("CHIMEDBRC"):
            _RC_FILES.insert(0, os.environ["CHIMEDBRC"])

    for rc_file in _RC_FILES:
        try:
            with open(rc_file) as f:
                rc = yaml.safe_load(f)

                # Nothing in this file, so skip it
                if rc is None:
                    continue

                # Create the connectors
                if section in rc:
                    conn = BaseConnector.from_dict(rc[section], rc_file)

                if conn is not None:
                    return conn

                # If we got here, things didn't work, so we try the next file
                logging.debug("Skipping invalid RC file {0}".format(rc_file))
        except IOError:
            pass

    # No valid file found
    return None


def connect(reconnect=False):
    """Connect to the CHIME Database.

    .. warning::
        Do not call this routine (or other routines that call it) during an
        import statement. This will cause the process to hang as the ssh tunnel
        attempts to create threads which can't acquire the global import lock.

    Parameters
    ----------
    reconnect : bool, optional
        Re-establish a connection even if one already exists.
    """

    # Initialise connections (only rank=0) if batch job.
    if not connect_this_rank():
        return

    current_connector = getattr(_threadlocal, "current_connector", None)
    current_connector_RW = getattr(_threadlocal, "current_connector_RW", None)

    if not reconnect and (
        current_connector is not None or current_connector_RW is not None
    ):
        _logger.debug("Connection already exists.")
        return

    # Check for CHIMEDB_TEST_ENABLE environtmental variable
    if _have_envvar("CHIMEDB_TEST_ENABLE"):
        test_enable()

    # First look for CHIMEDB_SQLITE
    sqlite_var = "CHIMEDB_TEST_SQLITE" if _TEST_ENABLE else "CHIMEDB_SQLITE"
    if _have_envvar(sqlite_var):
        connectors = [SqliteConnector(os.environ[sqlite_var], read_write=False)]
        connectors_rw = [SqliteConnector(os.environ[sqlite_var])]
        context = sqlite_var
    else:
        rc_data = _try_rc_files()

        if rc_data:
            connectors, connectors_rw, context = rc_data
        elif _TEST_ENABLE:
            # Make an in-memory sqlite database
            connectors = [
                SqliteConnector("file::memory:?cache=shared", read_write=False)
            ]
            connectors_rw = [SqliteConnector("file::memory:?cache=shared")]
            context = "_TEST_ENABLE"
        else:
            try:
                from chimedb.config import connectors, connectors_rw
            except ImportError as e:
                raise NoRouteToDatabase(
                    "Unable to find connection configuration for the database!"
                    "Either provide a chimedb RC file in one of the default"
                    "locations or install `chimedb.config`."
                ) from e
            else:
                context = "chimedb.config"

    # Try to connect, these will raise  ConnectionError on error
    _initialize_connections(connectors, context)
    _initialize_connections(connectors_rw, context, True)

    # If that succeeded, remember the connectors
    current_connector = getattr(_threadlocal, "current_connector", None)
    current_connector_RW = getattr(_threadlocal, "current_connector_RW", None)

    if current_connector is None or current_connector_RW is None:
        raise ConnectionError(
            "Connection data found, but no connection could be established."
        )


def close():
    """Close all open database connections."""
    current_connector = getattr(_threadlocal, "current_connector", None)
    if current_connector:
        current_connector.close()
        _threadlocal.current_connector = None
    current_connector_RW = getattr(_threadlocal, "current_connector_RW", None)
    if current_connector_RW:
        current_connector_RW.close()
        _threadlocal.current_connector_RW = None
