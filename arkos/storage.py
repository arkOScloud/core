"""
Classes to manage internal object cache.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""


class StorageControl:
    """The primary controller for all Storage classes."""

    def __init__(self):
        """Initialize arkOS storage."""
        self.apps = Storage(["applications"])
        self.sites = Storage(["sites"])
        self.certs = Storage(["certificates", "authorities"])
        self.dbs = Storage(["databases", "users", "managers"])
        self.points = Storage(["points"])
        self.updates = Storage(["updates"])
        self.policies = Storage(["policies"])
        self.files = Storage(["sharedfiles"])
        self.shares = Storage(["shares", "mounts", "sharers"])
        self.signals = Storage(["listeners"])


class Storage:
    """Represents memory storage for different types of arkOS objects."""

    def __init__(self, types=[]):
        """
        Initialize memory storage object.

        :param list types: List of subtypes for this storage type
        """
        for x in types:
            setattr(self, x, [])

    def add(self, stype, item):
        """
        Add an object to storage list.

        :param str stype: Storage subtype
        :param item: Object to store
        """
        s = getattr(self, stype)
        s.append(item)

    def set(self, stype, items):
        """
        Set an object storage list.

        :param str stype: Storage subtype
        :param list items: List of object(s) to store
        """
        setattr(self, stype, items)

    def get(self, stype, id=None):
        """
        Retrieve an object (or objects) from storage.

        If ``id`` is not specified, all objects returned.

        :param str stype: Storage subtype
        :param str id: Object's ID property
        :returns: object or list of objects
        """
        s = getattr(self, stype)
        if id:
            for x in s:
                if id == x.id:
                    return x
            return None
        return s

    def get_keyed(self, stype, id=None):
        """
        Retrieve objects from storage, via a dictionary keyed by object ID.

        :param str stype: Storage subtype
        """
        items = {}
        s = getattr(self, stype)
        for x in s:
            items[x.id] = x
        return items

    def remove(self, stype, item):
        """
        Remove object from storage.

        :param str stype: Storage subtype
        :param item: Object
        """
        s = getattr(self, stype)
        if type(item) == str:
            for x in s:
                if item == x.id:
                    s.remove(x)
                    return
        elif item in s:
            s.remove(item)
