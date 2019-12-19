import os
import sqlite3
import tempfile
import unittest
import peewee as pw
import chimedb.core as db
from unittest.mock import patch
from chimedb.core.orm import base_model


class TestTable(base_model):
    datum = pw.IntegerField()


datum_value = 83


class TestDecorator(unittest.TestCase):
    """Test chimedb.core.session"""

    def tearDown(self):
        db.close()
        os.remove(self.dbfile)

        self.patched_env.stop()

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

        self.patched_env = patch.dict(
            os.environ, {"CHIMEDB_TEST_SQLITE": self.dbfile, "CHIMEDB_TEST_ENABLE": "1"}
        )
        self.patched_env.start()

    def test_atomic_rollback(self):
        @db.atomic(read_write=True)
        def inside_atomic():
            TestTable.update(datum=datum_value + 1).execute()

            db.proxy.rollback()

        # Execute
        inside_atomic()

        # Check
        db.close()
        db.connect()
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value)

    def test_atomic_commit(self):
        @db.atomic(read_write=True)
        def inside_atomic():
            TestTable.update(datum=datum_value + 1).execute()

            db.proxy.commit()

        # Execute
        inside_atomic()

        # Check
        db.close()
        db.connect()
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value + 1)

    def test_atomic_raise(self):
        @db.atomic(read_write=True)
        def inside_atomic():
            TestTable.update(datum=datum_value + 1).execute()

            raise RuntimeError

        # Execute
        with self.assertRaises(RuntimeError):
            inside_atomic()

        # Check
        db.close()
        db.connect()
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value)

    def test_atomic_autocommit(self):
        @db.atomic(read_write=True)
        def inside_atomic():
            TestTable.update(datum=datum_value + 1).execute()

        # Execute
        inside_atomic()

        # Check
        db.close()
        db.connect()
        self.assertEqual(TestTable.select(TestTable.datum).scalar(), datum_value + 1)


if __name__ == "__main__":
    unittest.main()
