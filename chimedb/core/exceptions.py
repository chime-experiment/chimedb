"""
Basic CHIME-db related exceptions.
"""
# === Start Python 2/3 compatibility
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614

# === End Python 2/3 compatibility


class CHIMEdbError(RuntimeError):
    """The base chimedb exception."""


class NotFoundError(CHIMEdbError):
    """A search failed."""


class ValidationError(CHIMEdbError):
    """Validation of a name or field failed."""


class InconsistencyError(CHIMEdbError):
    """Internal inconsistency exists with the database."""


class AlreadyExistsError(CHIMEdbError):
    """A record already exists in the database."""


class ConnectionError(CHIMEdbError):
    """An error occurred when trying to connect to the database"""


class NoRouteToDatabase(ConnectionError):
    """No route was found to the database."""
