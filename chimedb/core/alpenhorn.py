"""Alpenhorn-2 integration.

Provides an extension module for alpenhorn-2.
"""

import peewee as pw

from . import connectdb
from .exceptions import ConnectionError, NoRouteToDatabase


def connect(config):
    """connectdb.connect() boilperplate"""
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
    """Register an alpenhorn database extension."""
    return {
        "database": {"connect": connect, "close": connectdb.close, "reentrant": True}
    }
