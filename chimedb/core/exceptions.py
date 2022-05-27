"""
Basic CHIME-db related exceptions.
"""


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
