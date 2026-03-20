"""Tunnelling SSH server.

This provides the ConnectionTunnel thread which implements an
SSH client which can tunnel a database port from another, remote host.
"""

import asyncio
import os
import logging
import threading
import time

import asyncssh

from .exceptions import NoRouteToDatabase

_logger = logging.getLogger("chimedb")

# We only ever run one tunnel thread.  This is it
_thread = None

# Mutex for _thread
_thread_lock = threading.Lock()


class ConnectionTunnel(threading.Thread):
    """A SSH-tunnelling thread.

    Attributes
    ----------
    tunnel_host : str
        The host to tunnel through
    tunnel_user : str
        The username used to log into the tunnel host
    tunnel_identity : Pathlike | None
        If not None, a path to a SSH identity to use to authenticate with the
        tunnel host.  If None, authentication will be attempted via SSH agent
        and/or keys found locally.
    remote_host : str
        The remote host to tunnel
    remote_port : int
        The remote poirt to tunnel
    """

    def __init__(
        self,
        tunnel_host: str,
        tunnel_user: str,
        tunnel_identity: str | os.PathLike | None,
        remote_host: str,
        remote_port: int,
    ) -> None:
        # Connection and tunnel details
        self._tunnel_host = tunnel_host
        self._remote_host = remote_host
        self._remote_port = remote_port

        # Choose auth parameters based on whether we have been given an ident or not
        if tunnel_identity:
            auth_opts = {"client_keys": [tunnel_identity], "agent_path": None}
        else:
            # Use configuration defaults, in this case, which will try both an agent, and
            # also look for local keys
            auth_opts = {}

        # Set SSH client options
        self._ssh_opts = asyncssh.SSHClientConnectionOptions(
            username=tunnel_user, **auth_opts
        )

        # This is set when the tunnel is active
        self.tunnel_port = None

        # Set to True to shut down the tunnel
        self._stop_the_tunnel = False

        # Thread init
        super().__init__(name="ConnectionTunnel", daemon=True)

    async def ssh_client(self):
        """The SSH client that does the forwarding."""

        try:
            async with asyncssh.connect(
                self._tunnel_host, options=self._ssh_opts
            ) as conn:
                # Bind the listener to an ephemeral port
                listener = await conn.forward_local_port(
                    "", 0, self._remote_host, self._remote_port
                )

                # Tunnel active: record port
                self.tunnel_port = listener.get_port()

                _logger.debug(
                    f"SSH tunnel via {self._tunnel_host} established on port {self.tunnel_port}"
                )

                # Wait for termination
                while not self._stop_the_tunnel:
                    await asyncio.sleep(0.1)

                # Close the connection
                _logger.debug("Terminating tunnel: shutdown requested.")
                listener.close()
                await listener.wait_closed()
        except asyncio.CancelledError:
            _logger.debug(f"SSH tunnel via {self._tunnel_host} stopped")
            raise
        except asyncssh.misc.ConnectionLost as e:
            _logger.warning(f"Connection to {self._tunnel_host} lost: {e}")
            raise NoRouteToDatabase(f"Error in SSH tunnel: {e}") from e
        except (OSError, asyncssh.Error) as e:
            _logger.warning(f"SSH tunnel via {self._tunnel_host} aborted: {e}")
            raise NoRouteToDatabase(f"Error in SSH tunnel: {e}") from e
        finally:
            # Tunnel no longer active
            self.tunnel_port = None
            self._stop_the_tunnel = False

    def run(self):
        """Tunnelling SSH server implementation."""

        # Start the asyncio loop
        asyncio.run(self.ssh_client())

    def join(self):
        """Terminate the tunnel."""

        # Cancel the client, if running
        _logger.debug("Joining...")
        if self.tunnel_port:
            self._stop_the_tunnel = True

        # Join the thread
        return super().join()


def active() -> bool:
    """Is the tunnel active?"""
    global _thread, _thread_lock
    with _thread_lock:
        if _thread is None:
            return False
        if not _thread.is_alive():
            return False
        return _thread.tunnel_port is not None


def port() -> int:
    """Return the tunnel's local port number.

    If the tunnel isn't running, this returns None.
    """
    with _thread_lock:
        if _thread and _thread.is_alive():
            return _thread.tunnel_port

    return None


def start(
    tunnel_host: str,
    tunnel_user: str,
    tunnel_identity: str | os.PathLike | None,
    remote_host: str,
    remote_port: int,
) -> bool:
    """Start tunnelling.

    Waits for the tunnel to be established, or for the ssh client to exit.

    If a tunnel is already active, this does nothing.

    Parameters
    ----------
    tunnel_host : str
        The host to tunnel through
    tunnel_user : str
        The username used to log into the tunnel host
    tunnel_identity : Pathlike | None
        If not None, a path to a SSH identity to use to authenticate with the
        tunnel host.  If None, authentication will be attempted via SSH agent
        and/or keys found locally.
    remote_host : str
        The remote host to tunnel
    remote_port : int
        The remote port to tunnel

    Returns
    -------
    bool
        True if the tunnel successfully started.  False otherwise.
    """
    global _thread, _thread_lock

    # Clean up a dead tunnel, if it's still around.
    with _thread_lock:
        if _thread is not None and not _thread.is_alive():
            # Thread is done
            _thread = None

    # If the thread is not running, start it
    with _thread_lock:
        if _thread is None:
            _logger.debug(
                f"Attempting to tunnel through {tunnel_user}@{tunnel_host}..."
            )
            # Create new thread
            _thread = ConnectionTunnel(
                tunnel_host, tunnel_user, tunnel_identity, remote_host, remote_port
            )

            # Start it
            _thread.start()

    # Wait for the tunneling to start, or for the thread to exit
    while True:
        # Wait a bit
        time.sleep(0.1)
        with _thread_lock:
            if not _thread:
                # Someone else cleaned up while we were waiting
                return False
            if not _thread.is_alive():
                # Thread is done
                _thread = None
                return False
            if _thread.tunnel_port is not None:
                # Tunnel is active
                return True


def stop() -> bool:
    """Stop the tunnel, if active."""
    global _thread, _thread_lock

    with _thread_lock:
        if _thread is not None:
            while _thread.is_alive():
                _thread.join()
            _thread = None
