import chimedb.core as db

import os
import pytest
import tempfile

user = "Test"
user_id = 0
fail_user = "Fail"
password = "******"


@pytest.fixture
def db_conn():
    """Set up chimedb.core for testing with a local dummy DB."""
    (fd, rcfile) = tempfile.mkstemp(text=True)
    os.close(fd)

    # Tell chimedb where the database connection config is
    assert os.path.isfile(rcfile), "Could not find {}.".format(rcfile)

    os.environ["CHIMEDB_TEST_SQLITE"] = rcfile
    # Make sure we don't write to the actual chime database
    os.environ["CHIMEDB_TEST_ENABLE"] = "Yes, please."

    db.connect()
    db.orm.create_tables(["chimedb.dataflag.opinion"])

    # insert a user
    pwd = ":B:0000ffff:e989651ffffcb5bf9b9abedfdab58460"
    db.mediawiki.MediaWikiUser.get_or_create(
        user_id=user_id, user_name=user, user_password=pwd
    )

    # insert a user with a password hash we don't understand
    pwd = "1 2 3 4"
    db.mediawiki.MediaWikiUser.get_or_create(
        user_id=1, user_name=fail_user, user_password=pwd
    )
    db.close()

    yield

    # tear down
    os.remove(rcfile)


def test_user_authentication(db_conn):
    with pytest.raises(db.exceptions.ValidationError):
        db.mediawiki.MediaWikiUser.authenticate(fail_user, password)

    with pytest.raises(UserWarning):
        db.mediawiki.MediaWikiUser.authenticate("unknown_user", password)

    with pytest.raises(UserWarning):
        db.mediawiki.MediaWikiUser.authenticate(user, "wrong_password")

    assert db.mediawiki.MediaWikiUser.authenticate(user, password) is not None

    db.close()
