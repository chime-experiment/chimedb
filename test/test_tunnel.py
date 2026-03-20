"""Test tunnelling."""

import os
import socket
import subprocess
import threading
import time

import pytest

from chimedb.core import tunnel

# Data from the "database"
DATA = b"I'm a database server!"


class TCPServer(threading.Thread):
    """A very simple TCP server."""

    def __init__(self):
        # Port we're listening on.  Will be filled in when the server starts
        self.port = None

        # Set this to True to stop the server
        self._shutdown = False

        super().__init__(name="TCPServer", daemon=True)

    def shutdown(self):
        self._shutdown = True

    def run(self):
        # Create a TCP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Set timeout
        sock.settimeout(1)

        # Bind
        sock.bind(("127.0.0.1", 0))

        # Get bound port number
        self.port = sock.getsockname()[1]

        # Listen
        sock.listen(1)

        # Pretend to be a database server
        while not self._shutdown:
            try:
                conn, peer = sock.accept()
            except TimeoutError:
                continue

            try:
                conn.send(DATA)
            finally:
                conn.close()

        # Shutdown
        self.port = None
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            # Socket not connected
            pass

        sock.close()


@pytest.fixture
def fake_dbms():
    """Create a fake database server that we can tunnel.

    Yields the port on which the server is listening.
    """

    # Start database thread
    db = TCPServer()

    db.start()

    # Wait for start
    while db.is_alive() and db.port is None:
        time.sleep(0.1)

    # Run the test
    yield db.port

    # Shutdown
    db.shutdown()
    while db.is_alive():
        db.join()


@pytest.fixture
def stop_tunnel():
    """Ensure tunnels stop after a test."""

    # Run the test
    yield

    # If no tunnel is running, this is a NOP
    tunnel.stop()


def test_tunnel(fake_dbms, stop_tunnel):
    """Test tunnelling."""

    # Only run this test is we can SSH to localhost
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "127.0.0.1", "echo This worked."],
        capture_output=True,
        text=True,
    )
    if result.returncode or result.stdout != "This worked.\n":
        pytest.skip("Can't SSH to localhost")

    tunnel.start(
        tunnel_host="127.0.0.1",
        tunnel_user=os.getlogin(),
        tunnel_identity=None,
        remote_host="127.0.0.1",
        remote_port=fake_dbms,
    )

    # Port is set
    port = tunnel.port()
    assert port is not None

    # Read data
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))
    assert sock.recv(len(DATA)) == DATA
    sock.close()

    # Stop the tunnel
    tunnel.stop()

    # No tunnel port anymore
    assert tunnel.port() is None

    # We should be able to do this again
    tunnel.stop()

    # Still no tunnel
    assert tunnel.port() is None
