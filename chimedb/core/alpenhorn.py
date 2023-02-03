"""Alpenhorn-2 integration.

Provides a database extension module for alpenhorn-2 which
connects chimedb and alpenhorn, allowing alpenhorn to use this
package for database access.

See `alpenhorn.extensions` and `alpenhorn.db` for more details
on what an alpenhorn database extension is.
"""

import peewee as pw

from . import connectdb
from .exceptions import ConnectionError, NoRouteToDatabase


def connect(config):
    """Connect to the CHIMEDB for alpenhorn use.

    This is a wrapper around `connectdb.connect` which will be called by
    `alpenhorn` to establish a database connection.

    The `peewee.Database` from the read-write connector is returned
    to alpenhorn.

    Parameters
    ----------
    config : dict
        Ignored.  This is the parsed contents of the "database" section of the
        alpenhorn config file.  This function ignores this configuration
        data: set up CHIMEDB in the usual way to use it with alpenhorn.

    Raises
    ------
    peewee.OperationalError
        On database connection failure
    """
    try:
        connectdb.connect()
    except (NoRouteToDatabase, ConnectionError) as e:
        raise pw.OperationalError("chimedb connection failed") from e

    # Retrieve the database connection
    connector = connectdb.current_connector(read_write=True)

    if not connector:
        raise pw.OperationalError("No database connection could be established.")

    return connector.get_peewee_database()


def register_extension():
    """Register an alpenhorn database extension.

    Returns a "capability dict" providing the database capabilities of this
    database module to alpenhorn.
    """
    return {
        "database": {"connect": connect, "close": connectdb.close, "reentrant": True}
    }
