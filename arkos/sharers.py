"""
Classes and functions for managing file sharing services.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos import storage, signals, applications


class Sharer:
    """
    Represents a file sharing service.

    A file sharing service can be designed to operate either on a local area
    network, or instead to be a sync client for devices on the Internet.
    """

    def __init__(self, service_id="", name="", icon=""):
        """
        Initialize the sharer object.

        :param str service_id: File sharing service ID
        :param str name: File sharing service display name
        :param str icon: FontAwesome icon class
        """
        self.id = id
        self.name = name
        self.icon = icon

    def get_shares(self):
        """Reimplement this to return a list of Share objects."""

    @property
    def as_dict(self):
        """Return sharer metadata as dict."""
        return {
            "id": self.id,
            "name": self.name
        }

    @property
    def serialized(self):
        """Return serializable sharer metadata as dict."""
        return self.as_dict


class Share:
    """Represents a file share object."""

    def __init__(self, service_id="", comment="", path="", valid_users=[],
                 public=True, readonly=False, manager=None):
        """Initialize."""
        self.id = service_id
        self.comment = comment
        self.path = path
        self.valid_users = valid_users
        self.public = public
        self.readonly = readonly
        self.manager = manager

    def add_share(self):
        """Reimplement this with actions to add a share."""

    def remove_share(self):
        """Reimplement this with actions to remove a share."""

    def add(self, *args, **kwargs):
        """Add a file share."""
        signals.emit("shares", "pre_add", self)
        self.add_share()
        storage.files.add("shares", self)
        signals.emit("shares", "post_add", self)

    def remove(self, *args, **kwargs):
        """Remove a file share."""
        signals.emit("shares", "pre_remove", self)
        self.remove_share()
        storage.files.add("shares", self)
        signals.emit("shares", "post_remove", self)

    @property
    def as_dict(self):
        """Return share metadata as dict."""
        return {
            "id": self.id,
            "type": self.manager.id,
            "comment": self.comment,
            "path": self.path,
            "valid_users": self.valid_users,
            "public": self.public,
            "read_only": self.readonly
        }

    @property
    def serialized(self):
        """Return serializable share metadata as dict."""
        return self.as_dict


class Mount:
    """Represents a file share mount object."""

    def __init__(self, mount_id="", path="", network_path="", readonly=False,
                 is_mounted=False, manager=None):
        """Initialize."""
        self.id = mount_id
        self.path = path
        self.network_path = network_path
        self.readonly = readonly
        self.is_mounted = is_mounted
        self.manager = manager

    def mount(self):
        """Reimplement this with actions to mount a share."""

    def umount(self):
        """Reimplement this with actions to unmount a share."""

    def add(self, *args, **kwargs):
        """Mount a file share."""
        signals.emit("shares", "pre_mount", self)
        self.mount()
        storage.files.add("mounts", self)
        signals.emit("shares", "post_mount", self)

    def remove(self, *args, **kwargs):
        """Unmount a file share."""
        signals.emit("shares", "pre_umount", self)
        self.umount()
        storage.files.add("mounts", self)
        signals.emit("shares", "post_umount", self)

    @property
    def as_dict(self):
        """Return mount metadata as dict."""
        return {
            "id": self.id,
            "type": self.manager.id,
            "path": self.path,
            "network_path": self.network_path,
            "is_mounted": self.is_mounted,
            "read_only": self.readonly
        }

    @property
    def serialized(self):
        """Return serializable mount metadata as dict."""
        return self.as_dict


def get_shares(share_id=None, share_type=None):
    """
    Retrieve a list of all file shares registered with arkOS.

    :param str share_id: If present, obtain one share that matches this ID
    :param str share_type: Filter by ``fs-samba``, ``fs-afp``, etc
    :return: Share(s)
    :rtype: Share or list thereof
    """
    data = scan_shares()
    if share_id or share_type:
        tlist = []
        for x in data:
            if x.id == share_id:
                return x
            elif x.manager.id == share_type:
                tlist.append(x)
        if tlist:
            return tlist
        return None
    return data


def scan_shares():
    """
    Retrieve a list of all file shares registered with arkOS.

    :return: Share(s)
    :rtype: Share or list thereof
    """
    shares = []
    for x in get_sharers():
        try:
            shares += x.get_shares()
        except:
            continue
    storage.files.set("shares", shares)
    return shares


def get_mounts(mount_id=None, mount_type=None):
    """
    Retrieve a list of all file share mounts registered with arkOS.

    :param str mount_id: If present, obtain one mount that matches this ID
    :param str type: Filter by ``fs-samba``, ``fs-afp``, etc
    :return: Mount(s)
    :rtype: Mount or list thereof
    """
    data = scan_mounts()
    if mount_id or mount_type:
        tlist = []
        for x in data:
            if x.id == mount_id:
                return x
            elif x.manager.id == mount_type:
                tlist.append(x)
        if tlist:
            return tlist
        return None
    return data


def scan_mounts():
    """
    Retrieve a list of all file share mounts registered with arkOS.

    :return: Mount(s)
    :rtype: Mount or list thereof
    """
    mounts = []
    for x in get_sharers():
        try:
            mounts += x.get_mounts()
        except:
            continue
    storage.files.set("mounts", mounts)
    return mounts


def get_sharers(share_id=None):
    """
    Retrieve a list of all file share systems registered with arkOS.

    :param str id: If present, obtain one sharer that matches this ID
    :return: Sharer(s)
    :rtype: Sharer or list thereof
    """
    data = storage.files.get("sharers")
    if not data:
        data = scan_sharers()
    if share_id:
        for x in data:
            if x.id == share_id:
                return x
        return None
    return data


def scan_sharers():
    """
    Retrieve a list of all file share systems registered with arkOS.

    :return: Sharer(s)
    :rtype: Sharer or list thereof
    """
    mgrs = []
    for x in applications.get(type="fileshare"):
        if x.installed and hasattr(x, "_share_mgr"):
            mgrs.append(x._share_mgr(id=x.id, name=x.name, meta=x))
    storage.files.set("sharers", mgrs)
    return mgrs
