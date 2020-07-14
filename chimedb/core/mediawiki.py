from .orm import base_model
from .exceptions import ValidationError

import hashlib
import peewee as pw


class MediaWikiUser(base_model):
    """
    Represents a MediaWiki user.

    This is only a tiny subset of the actual table for MediaWiki >=1.23 .

    This is an incomplete table model which only provides user_name and user_password. While the
    datatype of these fields has never changed in any previous MediaWiki version, they may change
    in the future. This model was last verified against MediaWiki 1.34 (see
    https://www.mediawiki.org/wiki/Manual:User_table).

    This is meant to wrap a MySQL VIEW of the wiki table stored in a separate database.
    You can create this view with e.g (see
    https://dev.mysql.com/doc/refman/8.0/en/create-view.html):

        CREATE VIEW ch_data.mediawikiuser AS chimewiki.user


    Attributes
    ----------
    user_name : str
        The unique username. Starts with a capital letter.
    user_password : str
        The password hash. See https://www.mediawiki.org/wiki/Manual:User_table#user_password
    """

    user_id = pw.IntegerField(primary_key=True)
    user_name = pw.TextField()
    user_password = pw.TextField()

    @classmethod
    def authenticate(cls, user, password):
        """
        Authenticate mediaWiki user.

        The only supported password hashing algorithm supported is the antiquated "B" method
        (which we are restricted to by the layout database web front-end).
        See https://www.mediawiki.org/wiki/Manual:User_table#user_password.

        Parameters
        ----------
        user : str
            User name.
        password : str
            Password

        Returns
        -------
        MediaWikiUser
            If the login credentials are correct, the user object is returned, otherwise an
            exception is raised.

        Raises
        ------
        UserWarning
            If the login credentials don't match an existing user and password.
        ValidationError
            If a password stored in the database has a format that is not understood.
        """
        # UpperCase the first character of the username
        if not user or not isinstance(user, str) or len(user) < 1:
            raise UserWarning("Invalid value for username: %s" % user)
        if len(user) > 1:
            user = user[0].upper() + user[1:]
        else:
            user = user[0].upper()

        if not isinstance(password, str):
            raise UserWarning(
                "Value password has type '%s' (expected 'str')."
                % type(password).__name__
            )

        try:
            user_row = (
                MediaWikiUser.select(MediaWikiUser.user_id, MediaWikiUser.user_password)
                .where(MediaWikiUser.user_name == user)
                .get()
            )
        except pw.DoesNotExist:
            raise UserWarning("Wrong username or password.")
        stored_hash = user_row.user_password.split(":")

        # All passwords are currently stored in the following way, but MediaWiki supports different
        # hashing algorithms (see https://www.mediawiki.org/wiki/Manual:User_table#user_password).
        if len(stored_hash) != 4 or stored_hash[1] != "B":
            raise ValidationError(
                "'user_password' field for user '%s' has unknown format: %s"
                % (user, stored_hash)
            )
        _, _, salt, stored_hash = stored_hash

        salted_hash = salt + "-" + hashlib.md5(password.encode("utf-8")).hexdigest()
        hashed_salt = hashlib.md5(salted_hash.encode("utf-8")).hexdigest()
        if hashed_salt != stored_hash:
            raise UserWarning("Wrong username or password.")
        return user, user_row.user_id
