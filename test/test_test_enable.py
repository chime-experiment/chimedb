import os
import tempfile
import unittest
import peewee as pw
import chimedb.core as db
from unittest.mock import patch
from chimedb.core.orm import base_model


class TestTable(base_model):
    datum = pw.IntegerField()


datum_value = 84


class TestSafeMode(unittest.TestCase):
    """Test using test_enable() for testing"""

    def tearDown(self):
        self.patched_env.stop()

    def setUp(self):
        self.patched_env = patch.dict(os.environ)
        self.patched_env.start()

        if "CHIMEDB_TEST_ENABLE" in os.environ:
            del os.environ["CHIMEDB_TEST_ENABLE"]
        if "CHIMEDB_SQLITE" in os.environ:
            del os.environ["CHIMEDB_SQLITE"]
        if "CHIMEDBRC" in os.environ:
            del os.environ["CHIMEDBRC"]
        if "CHIMEDB_TEST_SQLITE" in os.environ:
            del os.environ["CHIMEDB_TEST_SQLITE"]
        if "CHIMEDB_TEST_RC" in os.environ:
            del os.environ["CHIMEDB_TEST_RC"]

    def test_chimedb_test_sqlite(self):
        # Create an empty on-disk sqlite database
        (fd, dbfile) = tempfile.mkstemp(text=True)
        os.close(fd)

        os.environ["CHIMEDB_TEST_SQLITE"] = dbfile

        db.test_enable()

        db.connect(read_write=True)
        db.proxy.create_tables([TestTable])
        TestTable.create(datum=datum_value)

        # Did that work?
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value)
        db.close()

        # The on-disk sqlite database should not be empty anymore
        stat = os.stat(dbfile)
        self.assertNotEqual(stat.st_size, 0)

    def test_chimedb_test_enable_envvar(self):
        # Like test_chimedb_test_sqlite, but using the envvar to turn on
        # test mode.
        (fd, dbfile) = tempfile.mkstemp(text=True)
        os.close(fd)

        os.environ["CHIMEDB_TEST_SQLITE"] = dbfile
        os.environ["CHIMEDB_TEST_ENABLE"] = "1"

        db.connect(read_write=True)
        db.proxy.create_tables([TestTable])
        TestTable.create(datum=datum_value)

        # Did that work?
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value)
        db.close()

        # The on-disk sqlite database should not be empty anymore
        stat = os.stat(dbfile)
        self.assertNotEqual(stat.st_size, 0)

    def test_chimedb_test_sqlite(self):
        # Create an empty on-disk sqlite database
        (fd, dbfile) = tempfile.mkstemp(text=True)
        os.close(fd)

        os.environ["CHIMEDB_TEST_SQLITE"] = dbfile

        db.test_enable()

        db.connect(read_write=True)
        db.proxy.create_tables([TestTable])
        TestTable.create(datum=datum_value)

        # Did that work?
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value)
        db.close()

        # The on-disk sqlite database should not be empty anymore
        stat = os.stat(dbfile)
        self.assertNotEqual(stat.st_size, 0)

    def test_chimedb_sqlite(self):
        # Create an empty on-disk sqlite database that won't be used
        (fd, dbfile) = tempfile.mkstemp(text=True)
        os.close(fd)

        # This should be ignored
        os.environ["CHIMEDB_SQLITE"] = dbfile

        db.test_enable()

        db.connect(read_write=True)
        db.proxy.create_tables([TestTable])
        TestTable.create(datum=datum_value)

        # Did that work?
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value)
        db.close()

        # The on-disk sqlite database should still be empty
        stat = os.stat(dbfile)
        self.assertEqual(stat.st_size, 0)
        os.remove(dbfile)

    def test_chimedbrc(self):
        # Create an empty on-disk sqlite database that won't be used
        (fd, dbfile) = tempfile.mkstemp(text=True)
        os.close(fd)

        # Create a rcfile
        (fd, rcfile) = tempfile.mkstemp(text=True)
        with os.fdopen(fd, "a") as rc:
            rc.write(
                """\
chimedb:
    db_type: sqlite
    db: {0}
""".format(
                    dbfile
                )
            )

        # This should be ignored
        os.environ["CHIMEDBRC"] = rcfile

        db.test_enable()

        db.connect(read_write=True)
        db.proxy.create_tables([TestTable])
        TestTable.create(datum=datum_value)

        # Did that work?
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value)
        db.close()

        # The on-disk sqlite database should still be empty
        stat = os.stat(dbfile)
        self.assertEqual(stat.st_size, 0)

        os.unlink(rcfile)
        os.unlink(dbfile)

    def test_chimedb_test_rc(self):
        # Create an empty on-disk sqlite database
        (fd, dbfile) = tempfile.mkstemp(text=True)
        os.close(fd)

        # Create a rcfile
        (fd, rcfile) = tempfile.mkstemp(text=True)
        with os.fdopen(fd, "a") as rc:
            rc.write(
                """\
chimedb:
    db_type: sqlite
    db: {0}
""".format(
                    dbfile
                )
            )

        # This should be ignored
        os.environ["CHIMEDB_TEST_RC"] = rcfile

        db.test_enable()

        db.connect(read_write=True)
        db.proxy.create_tables([TestTable])
        TestTable.create(datum=datum_value)

        # Did that work?
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value)
        db.close()

        # The on-disk sqlite database should not be empty
        stat = os.stat(dbfile)
        self.assertNotEqual(stat.st_size, 0)

        os.unlink(rcfile)
        os.unlink(dbfile)

    def test_no_chimedbrc(self):
        # This is not allowed
        os.environ["CHIMEDB_TEST_RC"] = 'any string containing "chimedbrc"'

        db.test_enable()

        with self.assertRaises(OSError):
            db.connect()


if __name__ == "__main__":
    unittest.main()
