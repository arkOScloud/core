"""
Classes and functions for managing databases and database engines.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos import storage, signals, applications
from arkos.utilities import errors


class Database:
    """
    Represents a database present on the system.

    Databases can be of various types, which can be installed via Database app
    extensions to arkOS. This class is to be reimplemented by each database
    app, and an instance created for each database found to be using that
    database engine.
    """

    def __init__(self, id="", manager=None):
        """
        Initialize the database object.

        :param str id: Database name
        :param DatabaseManager manager: Database manager object
        """
        self.id = id
        self.manager = manager

    def add(self):
        """
        Add a database.

        Calls the function declared in the subclass to execute actions as
        per that application's needs.
        """
        signals.emit("databases", "pre_add", self)
        try:
            self.add_db()
        except Exception as e:
            weberrors = (
                errors.InvalidConfigError,
                errors.OperationFailedError
            )
            if not isinstance(e, weberrors):
                raise errors.OperationFailedError(
                    "({0})".format(self.id)) from e
            else:
                raise
        finally:
            storage.dbs.add("databases", self)
            signals.emit("databases", "post_add", self)

    def add_db(self):
        """Add a database. Override in database app code."""
        pass

    def remove(self):
        """
        Remove a database.

        Calls the function declared in the subclass to execute actions as
        per that application's needs.
        """
        signals.emit("databases", "pre_remove", self)
        try:
            self.remove_db()
        except Exception as e:
            weberrors = (
                errors.InvalidConfigError,
                errors.OperationFailedError
            )
            if not isinstance(e, weberrors):
                raise errors.OperationFailedError(
                    "({0})".format(self.id)) from e
            else:
                raise
        finally:
            storage.dbs.remove("databases", self)
            signals.emit("databases", "post_remove", self)

    def remove_db(self):
        """Remove a database. Override in database app code."""
        pass

    def execute(self):
        """Execute SQL on a database. Override in database app code."""
        pass

    @property
    def as_dict(self):
        """Return database metadata as dict."""
        return {
            "id": self.id,
            "database_type": self.manager.id,
            "size": self.get_size(),
            "is_ready": True
        }

    @property
    def serialized(self):
        """Return serializable database metadata as dict."""
        return self.as_dict


class DatabaseUser:
    """
    Represents a database user present on the system.

    Database users can be of various types, which can be installed via Database
    app extensions to arkOS. Not all database types will require database
    users. This class is to be reimplemented by each database app, and an
    instance created for each database found to be using that database engine.
    """

    def __init__(self, id="", passwd="", manager=None):
        """
        Initialize the database user object.

        :param str id: User name
        :param str passwd: Database user password
        :param DatabaseManager manager: Database manager object
        """
        self.id = id
        self.passwd = passwd
        self.manager = manager

    def add(self, passwd):
        """
        Add a database user.

        Calls the function declared in the subclass to execute actions as
        per that application's needs.
        """
        signals.emit("databases", "pre_user_add", self)
        try:
            self.add_user(passwd)
        except Exception as e:
            weberrors = (
                errors.InvalidConfigError,
                errors.OperationFailedError
            )
            if not isinstance(e, weberrors):
                raise errors.OperationFailedError(
                    "({0})".format(self.id)) from e
            else:
                raise
        finally:
            storage.dbs.add("users", self)
            signals.emit("databases", "post_user_add", self)

    def add_user(self):
        """Add a database user. Override in database app code."""
        pass

    def remove(self):
        """
        Remove a database user.

        Calls the function declared in the subclass to execute actions as
        per that application's needs.
        """
        signals.emit("databases", "pre_user_remove", self)
        try:
            self.remove_user()
        except Exception as e:
            weberrors = (
                errors.InvalidConfigError,
                errors.OperationFailedError
            )
            if not isinstance(e, weberrors):
                raise errors.OperationFailedError(
                    "({0})".format(self.id)) from e
            else:
                raise
        finally:
            storage.dbs.remove("users", self)
            signals.emit("databases", "post_user_remove", self)

    def remove_user(self):
        """Remove a database user. Override in database app code."""
        pass

    def chperm(self):
        """Change database user permissions. Override in database app code."""
        pass

    @property
    def as_dict(self):
        """Return database user metadata as dict."""
        return {
            "id": self.id,
            "database_type": self.manager.id,
            "permissions": self.chperm("check"),
            "is_ready": True
        }

    @property
    def serialized(self):
        """Return serializable database metadata as dict."""
        return self.as_dict


class DatabaseManager:
    """
    Represents a database engine type present on the system.

    Database managers allow for the wholesale management of databases,
    including the instantiation of arkOS database and database user objects,
    as well as ensuring engine API connection and other things.
    """

    def __init__(self, id="", name="", meta=None):
        """
        Initialize the database manager.

        :param str id: Database mananger ID (``mariadb``)
        :param str name: Pretty database name (``MariaDB``)
        :param Application meta: Application metadata object
        """
        self.id = id
        self.name = name
        self.meta = meta
        self.state = True
        try:
            self.connect()
        except:
            pass

    def connect(self):
        """Connect to database engine API. Override in database app code."""
        pass

    def get_dbs(self):
        """
        Get a list of databases of this type. Override in database app code.

        :returns: list of Database objects
        """
        return []

    def add_db(self, name):
        """Convenience: to add a database. Override in database app code."""
        pass

    def get_users(self):
        """
        Get list of database users of this type. Override in database app code.

        :returns: list of DatabaseUser objects
        """
        return []

    def add_user(self, name, passwd):
        """Convenience: to add a user. Override in database app code."""
        pass

    @property
    def as_dict(self):
        """Return database manager metadata as dict."""
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "supports_users": self.meta.database_multiuser
        }

    @property
    def serialized(self):
        """Return serializable database manager metadata as dict."""
        return self.as_dict


def get(id=None, type=None):
    """
    Retrieve a list of all databases registered with arkOS.

    :param str id: If present, obtain one database that matches this ID
    :param str type: Filter by ``mariadb``, ``sqlite3``, etc
    :return: Database(s)
    :rtype: Database or list thereof
    """
    data = scan()
    if id or type:
        tlist = []
        for x in data:
            if x.id == id:
                return x
            elif x.manager.id == type:
                tlist.append(x)
        if tlist:
            return tlist
        return None
    return data


def scan():
    """
    Retrieve a list of all databases registered with arkOS.

    :return: Database(s)
    :rtype: Database or list thereof
    """
    dbs = []
    for x in get_managers():
        try:
            dbs += x.get_dbs()
        except:
            continue
    storage.dbs.set("databases", dbs)
    return dbs


def get_user(id=None, type=None):
    """
    Retrieve a list of all database users registered with arkOS.

    :param str id: If present, obtain one database user that matches this ID
    :param str type: Filter by ``mariadb``, ``sqlite3``, etc
    :return: DatabaseUser(s)
    :rtype: DatabaseUser or list thereof
    """
    data = scan_users()
    if id or type:
        tlist = []
        for x in data:
            if x.id == id:
                return x
            elif x.manager.id == type:
                tlist.append(x)
        if tlist:
            return tlist
        return None
    return data


def scan_users():
    """
    Retrieve a list of all database users registered with arkOS.

    :return: DatabaseUser(s)
    :rtype: DatabaseUser or list thereof
    """
    users = []
    for x in get_managers():
        try:
            users += x.get_users()
        except:
            continue
    storage.dbs.set("users", users)
    return users


def get_managers(id=None):
    """
    Retrieve a list of all database managers registered with arkOS.

    :param str id: If present, obtain one database manager that matches this ID
    :return: DatabaseManager(s)
    :rtype: DatabaseManager or list thereof
    """
    data = storage.dbs.get("managers")
    if not data:
        data = scan_managers()
    if id:
        for x in data:
            if x.id == id:
                return x
        return None
    return data


def scan_managers():
    """
    Retrieve a list of all database managers registered with arkOS.

    :return: DatabaseManager(s)
    :rtype: DatabaseManager or list thereof
    """
    mgrs = []
    for x in applications.get(type="database"):
        if x.installed and hasattr(x, "_database_mgr"):
            mgrs.append(x._database_mgr(id=x.id, name=x.name, meta=x))
    storage.dbs.set("managers", mgrs)
    return mgrs
