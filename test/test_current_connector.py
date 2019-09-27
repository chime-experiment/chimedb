import unittest
from chimedb.core import connectdb


class TestCurrentConnector(unittest.TestCase):
    """
    Some dumb test to make sure current_connector()
    can handle returning None when no connection has
    been made
    """

    def test_uninitialised_ro(self):
        self.assertEqual(connectdb.current_connector(), None)

    def test_uninitialised_rw(self):
        self.assertEqual(connectdb.current_connector(read_write=True), None)


if __name__ == "__main__":
    unittest.main()
