"""
Classes and functions for managing arkOS Shared Files.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos import storage
from arkos.system import systemtime


class SharedFile:
    """
    Class representing a Shared File.

    A Shared File is a file that has had a download link created for it. A user
    can choose a file or set of files to share to another user via the
    File Manager in Genesis. This core class is used uniquely for storing
    information on the shared files in the object cache. Actual serving of
    shared files is done through Kraken.
    """

    def __init__(self, id, path, expires=0):
        """
        Initialize the shared file.

        :param str id: shared file ID
        :param str path: path to file on disk
        :param int expires: Unix timestamp for expiry date/time; 0 for never
        """
        self.id = id
        self.path = path
        self.expires = expires
        self.fetch_count = 0

    def add(self):
        """Add a shared file reference to cache."""
        storage.files.add("sharedfiles", self)

    def delete(self):
        """Delete a shared file reference from cache."""
        storage.files.remove("sharedfiles", self)

    def update_expiry(self, nexpiry):
        """
        Update shared file expiry time.

        :param nexpiry: datetime representing expiry date/time; 0 for never
        """
        if nexpiry is False:
            self.expires = 0
        else:
            self.expires = systemtime.get_unix_time(nexpiry)

    @property
    def is_expired(self):
        """Return True if the object is already expired."""
        now = systemtime.get_unix_time()
        return (self.expires != 0 and self.expires < now)

    @property
    def as_dict(self):
        """Return shared file metadata as dict."""
        exp = systemtime.ts_to_datetime(self.expires, "unix")\
            if self.expires != 0 else ""
        return {
            "id": self.id,
            "path": self.path,
            "expires": self.expires != 0,
            "expires_at": exp,
            "fetch_count": self.fetch_count
        }

    @property
    def serialized(self):
        """Return serializable shared file metadata as dict."""
        data = self.as_dict
        data["expires_at"] = systemtime.get_iso_time(self.expires, "unix")\
            if self.expires != 0 else ""
        return data


def get(id=None):
    """List all shared file objects present in cache storage."""
    data = storage.files.get("sharedfiles")
    to_purge = []
    for x in data:
        if x.is_expired:
            to_purge.append(x)
    for x in to_purge:
        x.delete()
    if id:
        for x in data:
            if x.id == id:
                return x
        return None
    return data
