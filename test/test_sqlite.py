import os
import sqlite3
import tempfile
import unittest
import peewee as pw
from unittest.mock import patch
from chimedb.core.orm import base_model


class TestTable(base_model):
    datum = pw.IntegerField()


datum_value = 83


class TestSqlite(unittest.TestCase):
    """Rudemintary tests of connectdb using sqlite"""

    def tearDown(self):
        import chimedb.core as db

        self.patched_env.stop()
        db.close()
        os.remove(self.dbfile)

    def setUp(self):
        # Create a temporary file
        (fd, self.dbfile) = tempfile.mkstemp()
        os.close(fd)

        conn = sqlite3.connect(self.dbfile)
        curs = conn.cursor()

        curs.execute("CREATE TABLE testtable (datum INTEGER)")
        curs.execute("INSERT INTO testtable VALUES (?)", (datum_value,))

        conn.commit()
        conn.close()

        self.patched_env = patch.dict(os.environ, {"CHIMEDB_SQLITE": self.dbfile})
        self.patched_env.start()

    def test_connect(self):
        import chimedb.core as db

        db.connect()
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value)

    def test_connect_uri(self):
        os.environ["CHIMEDB_SQLITE"] = "file:" + self.dbfile
        self.test_connect()

    def test_connect_ro(self):
        import chimedb.core as db

        db.connect()
        with self.assertRaises(pw.OperationalError):
            TestTable.update(datum=datum_value * 2).execute()

    def test_connect_rw(self):
        import chimedb.core as db

        db.connect(read_write=True)
        TestTable.update(datum=datum_value * 2).execute()
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value * 2)

    def test_switch_connetion(self):
        import chimedb.core as db

        self.test_connect_ro()
        self.test_connect_rw()
        self.test_connect_ro()
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value * 2)

    def test_rcfile(self):
        # Create a temporary file
        (fd, rcfile) = tempfile.mkstemp(text=True)
        with os.fdopen(fd, "a") as rc:
            rc.write(
                """\
chimedb:
    db_type: sqlite
    db: {0}
""".format(
                    self.dbfile
                )
            )

        del os.environ["CHIMEDB_SQLITE"]
        os.environ["CHIMEDBRC"] = rcfile

        # We run this test to make sure BaseConnector.from_dict has made both
        # connectors correctly.
        self.test_switch_connetion()
        os.unlink(rcfile)


if __name__ == "__main__":
    unittest.main()
