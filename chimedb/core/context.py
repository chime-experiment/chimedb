"""CHIMEdb context management."""

import logging
import functools
import peewee as pw
from . import connect, proxy

# Set module logger.
_logger = logging.getLogger("chimedb")


def atomic(_func=None, **_kwargs):
    """peewee atomic function decorator

    Use this to decorate a function:

        @chimedb.core.atomic(read_write=True)
        def func():
            pass

    Then calling:

        func()

    is equivalent to:

        chimedb.core.connect(read_write=True)
        with chimedb.core.proxy.atomic():
            func()

    which ensures all database operations in func() occur in a transaction.

    If func() raises an exception, or calls sys.exit() with a non-zero return
    code, any pending transaction will be rolled back.  Otherwise any pending
    transaction will be automatically committed when func() exits.

    While within peewee's atomic() context, a transaction is always in progress.
    As a result, calling chimedb.core.close() from within func() is not allowed.

    This decorator can be used to wrap the invocation of a click group or command
    (including parameter callbacks).  To do so, place this decorator before the
    group or command decorator:

        @chimedb.core.atomic(read_write=True)
        @click.group()
        @click.option("--opt", type=CHIMEDB_ORM_TYPE)
        def group_name(opt):
            pass

    Parameters
    ----------
    `read_write` : bool
        If True, use a read-write connection to the database, otherwise
        a read-only connection will be established.
    """

    # Work-around for "def atomic(_func=None, *, read_write=False):" not working in Py2
    if "read_write" in _kwargs:
        read_write = _kwargs["read_write"]
    else:
        read_write = False

    def atomic_decorator(_func):
        # If this is a click group or command, shoe-horn ourselves into it by
        # monkey patching the main() method.
        _command = None
        try:
            import click

            if isinstance(_func, click.Command):
                _command = _func

                if getattr(_command, "__chimedb_diverted_main__", None):
                    # already monkey patched.  This decorator has nothing to do.
                    return _command

                _func = _command.main
                _command.__chimedb_diverted_main__ = _func
        except ImportError:
            pass

        def atomic_wrapper(*args, **kwargs):
            connect(read_write=read_write)

            saved_exit = None

            _logger.debug("Entering atomic context")
            with proxy.atomic() as transaction:
                try:
                    ret = _func(*args, **kwargs)
                except SystemExit as e:
                    if e.code:
                        _logger.debug("Non-zero SystemExit.code: rolling back")
                        transaction.rollback()
                    saved_exit = e
            _logger.debug("Exited atomic context")

            if saved_exit:
                _logger.debug("Raising delayed SystemExit")
                raise saved_exit
            return ret

        if _command:
            _command.main = functools.update_wrapper(atomic_wrapper, _func)
            return _command

        return functools.update_wrapper(atomic_wrapper, _func)

    if _func is None:
        return atomic_decorator
    return atomic_decorator(_func)
