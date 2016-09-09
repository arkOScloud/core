"""
Classes and functions for managing arkOS filesystem objects.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import ctypes
import ctypes.util
import glob
import os
import parted

from . import crypto
from . import losetup

from arkos import config, signals, sharers
from arkos.messages import Notification, NotificationThread
from arkos.utilities import shell

libc = ctypes.CDLL(ctypes.util.find_library("libc"), use_errno=True)


class DiskPartition:
    """Class for managing physical disk partitions."""

    def __init__(
            self, id="", path="", mountpoint=None, size=0, fstype="",
            enabled=False, crypt=False):
        """
        Initialize disk partition object.

        :param str id: partition name
        :param str path: device identifier
        :param str mountpoint: path to mointpoint (if mounted)
        :param int size: disk size in bytes
        :param str fstype: filesystem type ("ext4", "ntfs", etc)
        :param bool enabled: True if partition is mounted on boot
        :param bool crypt: True if partition is LUKS encrypted
        """
        self.id = id
        self.path = path
        self.mountpoint = mountpoint
        self.size = size
        self.fstype = fstype
        self.enabled = enabled
        self.crypt = crypt

    def is_mounted(self):
        """Return True if partition is mounted."""
        return self.mountpoint and os.path.ismount(self.mountpoint)

    def mount(self, passwd=None):
        """
        Mount partition.

        :param str passwd: If disk is encrypted, use this passphrase to unlock
        """
        if self.mountpoint and os.path.ismount(self.mountpoint):
            raise Exception("Disk partition already mounted")
        elif self.fstype == "Unknown":
            raise Exception("Cannot mount a partition of unknown type")
        signals.emit("filesystems", "pre_mount", self)
        mount_point = self.mountpoint or os.path.join("/media", self.id)
        luks_point = os.path.join("/dev/mapper", self.id)
        if not os.path.isdir(mount_point):
            os.makedirs(mount_point)
        if self.crypt and passwd:
            # Decrypt the disk first if it's an encrypted disk
            s = crypto.luks_open(self.path, self.id, passwd)
            if s != 0:
                excmsg = "Failed to decrypt {0} with errno {1}"
                raise Exception(excmsg.format(self.id, str(s)))
            s = libc.mount(ctypes.c_char_p(luks_point),
                           ctypes.c_char_p(mount_point),
                           ctypes.c_char_p(self.fstype), 0,
                           ctypes.c_char_p(""))
            if s == -1:
                crypto.luks_close(self.id)
                excmsg = "Failed to mount {0}: {1}"
                raise Exception(excmsg.format(self.id,
                                              os.strerror(ctypes.get_errno())))
        elif self.crypt and not passwd:
            raise Exception("Must provide password to decrypt encrypted disk")
        else:
            s = libc.mount(ctypes.c_char_p(self.path),
                           ctypes.c_char_p(mount_point),
                           ctypes.c_char_p(self.fstype), 0,
                           ctypes.c_char_p(""))
            if s == -1:
                excmsg = "Failed to mount {0}: {1}"
                raise Exception(excmsg.format(self.id,
                                              os.strerror(ctypes.get_errno())))
        signals.emit("filesystems", "post_mount", self)
        self.mountpoint = mount_point

    def umount(self):
        """Unmount partition."""
        signals.emit("filesystems", "pre_umount", self)
        if not self.mountpoint:
            return
        s = libc.umount2(ctypes.c_char_p(self.mountpoint), 0)
        if s == -1:
            excmsg = "Failed to unmount {0}: {1}"
            raise Exception(excmsg.format(self.id,
                                          os.strerror(ctypes.get_errno())))
        if self.crypt:
            crypto.luks_close(self.id)
        signals.emit("filesystems", "post_umount", self)
        self.mountpoint = None

    def enable(self):
        """Enable mounting of this partition on boot."""
        if self.crypt:
            raise Exception("Cannot enable encrypted virutal disks")
        f = FstabEntry()
        f.src = self.path
        f.dst = os.path.join("/media", self.id)
        f.uuid = get_partition_uuid_by_name(self.path)
        f.fs_type = "ext4"
        f.options = "defaults"
        f.dump_p = 0
        f.fsck_p = 0
        save_fstab_entry(f)
        if not os.path.exists(f.dst):
            os.makedirs(f.dst)
        self.enabled = True

    def disable(self):
        """Disable mounting of this partition on boot."""
        fstab = get_fstab()
        for x in fstab:
            if x == self.path:
                save_fstab_entry(fstab[x], remove=True)
                self.disabled = False
                break

    @property
    def as_dict(self):
        """Return partition metadata as dict."""
        return {
            "id": self.id,
            "type": "physical",
            "path": self.path,
            "mountpoint": self.mountpoint,
            "size": self.size,
            "fstype": self.fstype,
            "crypt": self.crypt,
            "enabled": self.enabled,
            "is_ready": True
        }

    @property
    def serialized(self):
        """Return serialized partition metadata as dict."""
        return self.as_dict


class VirtualDisk:
    """Class to manage virtual disk image objects."""

    def __init__(
            self, id="", path="", mountpoint=None, size=0, fstype="ext4",
            enabled=False, crypt=False):
        """
        Initialize virtual disk object.

        :param str id: partition name
        :param str path: device identifier
        :param str mountpoint: path to mointpoint (if mounted)
        :param int size: disk size in bytes
        :param str fstype: filesystem type ("ext4", "ntfs", etc)
        :param bool enabled: True if image is mounted on boot
        :param bool crypt: True if image is LUKS encrypted
        """
        self.id = id
        self.path = path
        self.mountpoint = mountpoint
        self.size = size
        self.fstype = fstype
        self.enabled = enabled
        self.crypt = crypt

    def create(self, mount=False, will_crypt=False,
               nthread=NotificationThread()):
        """
        Create virtual disk image.

        :param bool mount: Mount after creation?
        :param bool will_crypt: Will this disk be encrypted later?
        :param NotificationThread nthread: notification thread to use
        """
        nthread.title = "Creating virtual disk"

        vdisk_dir = config.get("filesystems", "vdisk_dir")
        if not os.path.exists(vdisk_dir):
            os.mkdir(vdisk_dir)
        self.path = str(os.path.join(vdisk_dir, self.id+".img"))
        if os.path.exists(self.path):
            raise Exception("This virtual disk already exists")

        # Create an empty file matching disk size
        signals.emit("filesystems", "pre_add", self)
        msg = "Creating virtual disk..."
        nthread.update(Notification("info", "Filesystems", msg))
        with open(self.path, "wb") as f:
            written = 0
            with open("/dev/zero", "r") as zero:
                while self.size > written:
                    written += 1024
                    f.write(zero.read(1024))

        if not will_crypt:
            # Get a free loopback device and mount
            loop = losetup.find_unused_loop_device()
            loop.mount(str(self.path), offset=1048576)
            # Make a filesystem
            msg = "Writing filesystem..."
            nthread.update(Notification("info", "Filesystems", msg))
            s = shell("mkfs.ext4 {0}".format(loop.device))
            if s["code"] != 0:
                excmsg = "Failed to format loop device: {0}"
                raise Exception(excmsg.format(s["stderr"]))
            loop.unmount()
            msg = "Virtual disk created successfully"
            nthread.complete(Notification("success", "Filesystems", msg))

        signals.emit("filesystems", "post_add", self)
        if mount:
            self.mount()

    def mount(self, passwd=None):
        """
        Mount partition.

        :param str passwd: If disk is encrypted, use this passphrase to unlock
        """
        if self.mountpoint and os.path.ismount(self.mountpoint):
            raise Exception("Virtual disk already mounted")
        signals.emit("filesystems", "pre_mount", self)
        if not os.path.isdir(os.path.join("/media", self.id)):
            os.makedirs(os.path.join("/media", self.id))
        mount_point = self.mountpoint or os.path.join("/media", self.id)
        luks_point = os.path.join("/dev/mapper", self.id)
        # Find a free loopback device and mount
        loop = losetup.find_unused_loop_device()
        loop.mount(str(self.path), offset=1048576)
        if self.crypt and passwd:
            # If it's an encrypted virtual disk, decrypt first then mount
            s = crypto.luks_open(loop.device, self.id, passwd)
            if s != 0:
                loop.unmount()
                excmsg = "Failed to decrypt {0} with errno {1}"
                raise Exception(excmsg.format(self.id, str(s)))
            s = libc.mount(ctypes.c_char_p(bytes(luks_point, 'utf-8')),
                           ctypes.c_char_p(bytes(mount_point, 'utf-8')),
                           ctypes.c_char_p(bytes(self.fstype, 'utf-8')), 0,
                           ctypes.c_char_p(b""))
            if s == -1:
                crypto.luks_close(self.id)
                loop.unmount()
                excmsg = "Failed to mount {0}: {1}"
                raise Exception(excmsg.format(self.id,
                                              os.strerror(ctypes.get_errno())))
        elif self.crypt and not passwd:
            excstr = "Must provide password to decrypt encrypted container"
            raise Exception(excstr)
        else:
            s = libc.mount(ctypes.c_char_p(loop.device),
                           ctypes.c_char_p(bytes(mount_point, 'utf-8')),
                           ctypes.c_char_p(bytes(self.fstype, 'utf-8')), 0,
                           ctypes.c_char_p(b""))
            if s == -1:
                loop.unmount()
                excstr = "Failed to mount {0}: {1}"
                raise Exception(excstr.format(self.id,
                                              os.strerror(ctypes.get_errno())))
        signals.emit("filesystems", "post_mount", self)
        self.mountpoint = mount_point

    def umount(self):
        """Unmount disk."""
        if not self.mountpoint:
            return
        signals.emit("filesystems", "pre_umount", self)
        loops = losetup.get_loop_devices()
        for l in loops:
            if loops[l].is_used() and loops[l].get_filename() == self.path:
                dev = loops[l]
                break
        s = libc.umount2(ctypes.c_char_p(self.mountpoint), 0)
        if s == -1:
            excstr = "Failed to unmount {0}: {1}"
            raise Exception(excstr.format(self.id,
                                          os.strerror(ctypes.get_errno())))
        if self.crypt:
            crypto.luks_close(self.id)
        if dev:
            dev.unmount()
        signals.emit("filesystems", "post_umount", self)
        self.mountpoint = None

    def enable(self):
        """Enable disk mounting on boot."""
        f = FstabEntry()
        f.src = self.path
        f.dst = os.path.join("/media", self.id)
        f.uuid = ""
        f.fs_type = "ext4"
        f.options = "loop,rw,auto"
        f.dump_p = 0
        f.fsck_p = 0
        save_fstab_entry(f)
        self.enabled = True

    def disable(self):
        """Disable mounting disk on boot."""
        fstab = get_fstab()
        for x in fstab:
            if x == self.path:
                save_fstab_entry(fstab[x], remove=True)
                self.enabled = False
                break

    def encrypt(self, passwd, cipher=config.get("filesystems", "cipher"),
                keysize=config.get("filesystems", "keysize"), mount=False):
        """
        Encrypt virtual disk image.

        :params str passwd: Passphrase to encrypt disk with
        :params str cipher: cipher suite to use (default aes-xts-plain64)
        :params str keysize: default key size to use (default 256)
        :params bool mount: mount after encrypt?
        """
        cipher = cipher or "aes-xts-plain64"
        keysize = keysize or 256
        vdisk_dir = config.get("filesystems", "vdisk_dir")
        os.rename(self.path, os.path.join(vdisk_dir, self.id+".crypt"))
        self.path = os.path.join(vdisk_dir, self.id+".crypt")
        # Find an open loopback device and mount
        loop = losetup.find_unused_loop_device()
        loop.mount(str(self.path), offset=1048576)
        # Encrypt the file inside the loopback and mount
        s = crypto.luks_format(loop.device, passwd, cipher, int(keysize))
        if s != 0:
            loop.unmount()
            os.rename(self.path, os.path.join(vdisk_dir, self.id+".img"))
            excstr = "Failed to encrypt {0} with errno {1}"
            raise Exception(excstr.format(self.id, str(s)))
        s = crypto.luks_open(loop.device, self.id, passwd)
        if s != 0:
            loop.unmount()
            excstr = "Failed to decrypt {0} with errno {1}"
            raise Exception(excstr.format(self.id, str(s)))
        # Create a filesystem inside the encrypted device
        s = shell("mkfs.ext4 /dev/mapper/{0}".format(self.id))
        crypto.luks_close(self.id)
        loop.unmount()
        if s["code"] != 0:
            excstr = "Failed to format loop device: {0}"
            raise Exception(excstr.format(s["stderr"]))
        self.crypt = True
        if mount:
            self.mount(passwd)

    def remove(self):
        """Delete virtual disk image."""
        self.umount()
        signals.emit("filesystems", "pre_remove", self)
        os.unlink(self.path)
        signals.emit("filesystems", "post_remove", self)

    @property
    def as_dict(self):
        """Return image metadata as dict."""
        return {
            "id": self.id,
            "type": "virtual",
            "path": self.path,
            "mountpoint": self.mountpoint,
            "size": self.size,
            "fstype": self.fstype,
            "enabled": self.enabled,
            "crypt": self.crypt,
            "is_ready": True
        }

    @property
    def serialized(self):
        """Return serializable image metadata as dict."""
        return self.as_dict


class PointOfInterest:
    """
    Class managing point of interest objects.

    A point of interest is a location on the filesystem that may be of interest
    to users on completing routine tasks, such as data directories of websites
    or mounted filesystems. They allow easy browsing in the file manager or
    selection for other tasks that require specification of a path.
    """

    def __init__(self, id="", path="", stype="", icon=""):
        """
        Initialize point of interest object.

        :param str id: point of interest name (site/app ID)
        :param str path: path to point
        :param str stype: point type (app, site, etc)
        :param str icon: FontAwesome icon class
        """
        self.id = id
        self.path = path
        self.stype = stype
        self.icon = icon

    @property
    def as_dict(self):
        """Return point of interest metadata as dict."""
        return {
            "id": self.id,
            "path": self.path,
            "type": self.stype,
            "icon": self.icon
        }

    @property
    def serialized(self):
        """Return serializable point of interest metadata as dict."""
        return self.as_dict


def get(id=None):
    """
    Get all physical disks and virtual disk images present on the system.

    :params str id: Return only the disk/image that matches this ID.
    :returns: DiskPartition(s) and/or VirtualDisk(s)
    :rtype: DiskPartition, VirtualDisk or a list thereof
    """
    devs, mps = [], {}
    fstab = get_fstab()
    vdisk_dir = config.get("filesystems", "vdisk_dir")

    # Get mount data for all devices
    with open("/etc/mtab", "r") as f:
        for x in f.readlines():
            x = x.split()
            mps[x[0]] = x[1]

    # Get physical disks available
    for d in parted.getAllDevices():
        try:
            parts = parted.Disk(d).getPrimaryPartitions()
        except:
            continue
        for p in parts:
            if p.path.split("/")[-1].startswith("loop"):
                continue
            try:
                fstype = parted.probeFileSystem(p.geometry)
            except:
                fstype = "Unknown"
            try:
                dev = DiskPartition(id=p.path.split("/")[-1], path=p.path,
                                    mountpoint=mps.get(p.path) or None,
                                    size=int(p.getSize("B")), fstype=fstype,
                                    enabled=p.path in fstab,
                                    crypt=crypto.is_luks(p.path) == 0)
                if id == dev.id:
                    return dev
                devs.append(dev)
            except:
                continue

    # Replace mount data for virtual disks with loopback id
    dd = losetup.get_loop_devices()
    for x in dd:
        try:
            s = dd[x].get_status()
        except:
            continue
        if "/dev/loop{0}".format(s.lo_number) in mps:
            mps[s.lo_filename] = mps["/dev/loop{0}".format(s.lo_number)]

    # Get virtual disks available
    for x in glob.glob(os.path.join(vdisk_dir, "*")):
        if not x.endswith((".img", ".crypt")):
            continue
        dname = os.path.splitext(os.path.split(x)[1])[0]
        luks_point = "/dev/mapper/{0}".format(dname)
        dev = VirtualDisk(id=dname, path=x, size=os.path.getsize(x),
                          mountpoint=mps.get(x) or mps.get(luks_point) or None,
                          enabled=x in fstab, crypt=x.endswith(".crypt"))
        if id == dev.id:
            return dev
        devs.append(dev)
    return devs if not id else None


def get_points(id=None, path=None):
    """
    Retrieve points of interest from the system.

    Points of interest are obtained at scan from websites and mounted disks.

    :param str id: If present, filter by point ID
    :param str path: Filter by filesystem path
    :return: Point(s)OfInterest
    :rtype: PointOfInterest or list thereof
    """
    points = []
    from arkos import websites
    for x in get():
        if x.mountpoint and x.mountpoint not in ["/", "/boot"]:
            p = PointOfInterest(x.id, x.mountpoint,
                                "crypt" if x.crypt else "disk",
                                "fa-hdd-o")
            points.append(p)
    for x in websites.get():
        if x.meta:
            p = PointOfInterest(x.id, x.data_path or x.path, "site",
                                x.meta.icon)
            points.append(p)
    for x in sharers.get_shares():
        p = PointOfInterest(x.id, x.path, "share", "fa-folder-open")
        points.append(p)
    for x in sharers.get_mounts():
        p = PointOfInterest(x.id, x.path, "mount", "fa-folder-open-o")
        points.append(p)
    if id:
        for x in points:
            if x.id == id:
                return x
        return None
    elif path:
        for x in points:
            if x.path == path:
                return x
        return None
    return points


class FstabEntry:
    """Class to manage entries in '/etc/fstab'."""

    def __init__(self):
        """Initialize fstab entry."""
        self.src = ""
        self.uuid = ""
        self.dst = ""
        self.options = ""
        self.fs_type = ""
        self.dump_p = 0
        self.fsck_p = 0


def get_fstab():
    """Get all fstab entries."""
    r = {}
    with open("/etc/fstab", "r") as f:
        ss = f.readlines()

    for s in ss:
        if not s.split() or s[0] == "#":
            continue
        s = s.split()
        e = FstabEntry()
        if s[0].startswith("UUID="):
            e.uuid = s[0].split("UUID=")[1]
            e.src = get_partition_name_by_uuid(e.uuid)
        else:
            e.src = s[0]
            e.uuid = get_partition_uuid_by_name(e.src)
        try:
            e.dst = s[1]
            e.fs_type = s[2]
            e.options = s[3]
            e.dump_p = int(s[4])
            e.fsck_p = int(s[5])
        except:
            pass
        r[e.src] = e
    return r


def save_fstab_entry(e, remove=False):
    """Format and save fstab entry."""
    lines = []
    uuid = "UUID={0}".format(e.uuid) if e.uuid else ""
    with open("/etc/fstab", "r") as f:
        for x in f.readlines():
            if x.startswith(e.src) or (uuid and x.startswith(uuid)):
                continue
            lines.append(x)
    if not remove:
        fstab_line = "{0}\t{1}\t{2}\t{3}\t{4}\t{5}\n"
        lines.append(fstab_line.format(uuid or e.src, e.dst, e.fs_type,
                                       e.options, e.dump_p, e.fsck_p))
    with open("/etc/fstab", "w") as f:
        f.writelines(lines)


def get_partition_uuid_by_name(p):
    """Get a partition's UUID from its device name."""
    return shell("blkid -o value -s UUID " + p)["stdout"].split(b"\n")[0]


def get_partition_name_by_uuid(u):
    """Get a partition's device name from its UUID."""
    return shell("blkid -U " + u)["stdout"].split(b"\n")[0]
