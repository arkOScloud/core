import ctypes, ctypes.util
import glob
import os
import parted
import re
import shutil

import crypto
import losetup

from arkos import config, signals
from arkos.utilities import shell

libc = ctypes.CDLL(ctypes.util.find_library("libc"), use_errno=True)


class DiskPartition:
    def __init__(
            self, id="", path="", mountpoint=None, size=0, fstype="",
            enabled=False, crypt=False):
        self.id = id
        self.path = path
        self.mountpoint = mountpoint
        self.size = size
        self.fstype = fstype
        self.enabled = enabled
        self.crypt = crypt

    def is_mounted(self):
        return self.mountpoint and os.path.ismount(self.mountpoint)

    def mount(self, passwd=None):
        if self.mountpoint and os.path.ismount(self.mountpoint):
            raise Exception("Disk partition already mounted")
        elif self.fstype == "Unknown":
            raise Exception("Cannot mount a partition of unknown type")
        signals.emit("filesystems", "pre_mount", self)
        mount_point = self.mountpoint if self.mountpoint else os.path.join("/media", self.id)
        if not os.path.isdir(mount_point):
            os.makedirs(mount_point)
        if self.crypt and passwd:
            # Decrypt the disk first if it's an encrypted disk
            s = crypto.luks_open(self.path, self.id, passwd)
            if s != 0:
                raise Exception("Failed to decrypt %s with errno %s" % (self.id, str(s)))
            s = libc.mount(ctypes.c_char_p(os.path.join("/dev/mapper", self.id)),
                ctypes.c_char_p(mount_point),
                ctypes.c_char_p(self.fstype), 0, ctypes.c_char_p(""))
            if s == -1:
                crypto.luks_close(self.id)
                raise Exception("Failed to mount %s: %s" % (self.id, os.strerror(ctypes.get_errno())))
        elif self.crypt and not passwd:
            raise Exception("Must provide password to decrypt encrypted disk")
        else:
            s = libc.mount(ctypes.c_char_p(self.path),
                ctypes.c_char_p(mount_point),
                ctypes.c_char_p(self.fstype), 0, ctypes.c_char_p(""))
            if s == -1:
                raise Exception("Failed to mount %s: %s"%(self.id, os.strerror(ctypes.get_errno())))
        signals.emit("filesystems", "post_mount", self)
        self.mountpoint = mount_point

    def umount(self):
        signals.emit("filesystems", "pre_umount", self)
        if not self.mountpoint:
            return
        s = libc.umount2(ctypes.c_char_p(self.mountpoint), 0)
        if s == -1:
            raise Exception("Failed to unmount %s: %s"%(self.id, os.strerror(ctypes.get_errno())))
        if self.crypt:
            crypto.luks_close(self.id)
        signals.emit("filesystems", "post_umount", self)
        self.mountpoint = None

    def enable(self):
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
        fstab = get_fstab()
        for x in fstab:
            if x == self.path:
                save_fstab_entry(fstab[x], remove=True)
                self.disabled = False
                break

    @property
    def as_dict(self):
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
        return self.as_dict


class VirtualDisk:
    def __init__(
            self, id="", path="", mountpoint=None, size=0, fstype="ext4",
            enabled=False, crypt=False):
        self.id = id
        self.path = path
        self.mountpoint = mountpoint
        self.size = size
        self.fstype = fstype
        self.enabled = enabled
        self.crypt = crypt

    def create(self, mount=False):
        vdisk_dir = config.get("filesystems", "vdisk_dir")
        if not os.path.exists(os.path.join(config.get("filesystems", "vdisk_dir"))):
            os.mkdir(os.path.join(config.get("filesystems", "vdisk_dir")))
        self.path = str(os.path.join(vdisk_dir, self.id+".img"))
        if os.path.exists(self.path):
            raise Exception("This virtual disk already exists")
        signals.emit("filesystems", "pre_add", self)
        # Create an empty file matching disk size
        with open(self.path, "wb") as f:
            written = 0
            with file("/dev/zero", "r") as zero:
                while self.size > written:
                    written += 1024
                    f.write(zero.read(1024))
        # Get a free loopback device and mount
        loop = losetup.find_unused_loop_device()
        loop.mount(str(self.path), offset=1048576)
        # Make a filesystem
        s = shell("mkfs.ext4 %s" % loop.device)
        if s["code"] != 0:
            raise Exception("Failed to format loop device: %s" % s["stderr"])
        loop.unmount()
        signals.emit("filesystems", "pre_add", self)
        if mount:
            self.mount()

    def mount(self, passwd=None):
        if self.mountpoint and os.path.ismount(self.mountpoint):
            raise Exception("Virtual disk already mounted")
        signals.emit("filesystems", "pre_mount", self)
        if not os.path.isdir(os.path.join("/media", self.id)):
            os.makedirs(os.path.join("/media", self.id))
        mount_point = self.mountpoint if self.mountpoint else os.path.join("/media", self.id)
        # Find a free loopback device and mount
        loop = losetup.find_unused_loop_device()
        loop.mount(str(self.path), offset=1048576)
        if self.crypt and passwd:
            # If it's an encrypted virtual disk, decrypt first then mount
            s = crypto.luks_open(loop.device, self.id, passwd)
            if s != 0:
                loop.unmount()
                raise Exception("Failed to decrypt %s with errno %s" % (self.id, str(s)))
            s = libc.mount(ctypes.c_char_p(os.path.join("/dev/mapper", self.id)),
                ctypes.c_char_p(mount_point),
                ctypes.c_char_p(self.fstype), 0, ctypes.c_char_p(""))
            if s == -1:
                crypto.luks_close(self.id)
                loop.unmount()
                raise Exception("Failed to mount %s: %s" % (self.id, os.strerror(ctypes.get_errno())))
        elif self.crypt and not passwd:
            raise Exception("Must provide password to decrypt encrypted container")
        else:
            s = libc.mount(ctypes.c_char_p(loop.device), ctypes.c_char_p(mount_point),
                ctypes.c_char_p(self.fstype), 0, ctypes.c_char_p(""))
            if s == -1:
                loop.unmount()
                raise Exception("Failed to mount %s: %s" % (self.id, os.strerror(ctypes.get_errno())))
        signals.emit("filesystems", "post_mount", self)
        self.mountpoint = mount_point

    def umount(self):
        if not self.mountpoint:
            return
        signals.emit("filesystems", "pre_umount", self)
        loops = losetup.get_loop_devices()
        for loop in loops:
            if loops[loop].is_used() and loops[loop].get_filename() == self.path:
                dev = loops[loop]
                break
        s = libc.umount2(ctypes.c_char_p(self.mountpoint), 0)
        if s == -1:
            raise Exception("Failed to unmount %s: %s" % (self.id, os.strerror(ctypes.get_errno())))
        if self.crypt:
            crypto.luks_close(self.id)
        if dev:
            dev.unmount()
        signals.emit("filesystems", "post_umount", self)
        self.mountpoint = None

    def enable(self):
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
        fstab = get_fstab()
        for x in fstab:
            if x == self.path:
                save_fstab_entry(fstab[x], remove=True)
                self.enabled = False
                break

    def encrypt(self, passwd, cipher="", keysize=0, mount=False):
        cipher = cipher or config.get("filesystems", "cipher") or "aes-xts-plain64"
        keysize = keysize or config.get("filesystems", "keysize") or 256
        os.rename(self.path, os.path.join(config.get("filesystems", "vdisk_dir"), self.id+".crypt"))
        self.path = os.path.join(config.get("filesystems", "vdisk_dir"), self.id+".crypt")
        # Find an open loopback device and mount
        loop = losetup.find_unused_loop_device()
        loop.mount(str(self.path), offset=1048576)
        # Encrypt the file inside the loopback and mount
        s = crypto.luks_format(loop.device, passwd, cipher, int(keysize))
        if s != 0:
            loop.unmount()
            os.rename(self.path, os.path.join(config.get("filesystems", "vdisk_dir"), self.id+".img"))
            raise Exception("Failed to encrypt %s with errno %s"%(self.id, str(s)))
        s = crypto.luks_open(loop.device, self.id, passwd)
        if s != 0:
            loop.unmount()
            raise Exception("Failed to decrypt %s with errno %s"%(self.id, str(s)))
        # Create a filesystem inside the encrypted device
        s = shell("mkfs.ext4 /dev/mapper/%s" % self.id)
        crypto.luks_close(self.id)
        loop.unmount()
        if s["code"] != 0:
            raise Exception("Failed to format loop device: %s" % s["stderr"])
        self.crypt = True
        if mount:
            self.mount(passwd)

    def remove(self):
        self.umount()
        signals.emit("filesystems", "pre_remove", self)
        os.unlink(self.path)
        signals.emit("filesystems", "post_remove", self)

    @property
    def as_dict(self):
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
        return self.as_dict


class PointOfInterest:
    def __init__(self, id="", path="", stype="", icon=""):
        self.id = id
        self.path = path
        self.stype = stype
        self.icon = icon

    @property
    def as_dict(self):
        return {
            "id": self.id,
            "path": self.path,
            "type": self.stype,
            "icon": self.icon
        }

    @property
    def serialized(self):
        return self.as_dict


def get(id=None):
    devs, mps = [], {}
    fstab = get_fstab()

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
                    mountpoint=mps.get(p.path) or None, size=int(p.getSize("B")),
                    fstype=fstype, enabled=p.path in fstab, crypt=crypto.is_luks(p.path)==0)
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
        if "/dev/loop%s" % s.lo_number in mps:
            mps[s.lo_filename] = mps["/dev/loop%s" % s.lo_number]

    # Get virtual disks available
    for x in glob.glob(os.path.join(config.get("filesystems", "vdisk_dir"), "*")):
        if not x.endswith((".img", ".crypt")):
            continue
        dname = os.path.splitext(os.path.split(x)[1])[0]
        dev = VirtualDisk(id=dname, path=x, size=os.path.getsize(x),
            mountpoint=mps.get(x) or mps.get("/dev/mapper/%s" % dname) or None,
            enabled=x in fstab, crypt=x.endswith(".crypt"))
        if id == dev.id:
            return dev
        devs.append(dev)
    return devs if not id else None

def get_points(id=None, path=None):
    points = []
    from arkos import websites
    for x in get():
        if x.mountpoint and not x.mountpoint in ["/", "/boot"]:
            p = PointOfInterest(x.id, x.mountpoint, "crypt" if x.crypt else "disk", "fa-hdd-o")
            points.append(p)
    for x in websites.get():
        if x.meta:
            p = PointOfInterest(x.id, x.data_path or x.path, "site", x.meta.icon)
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
    def __init__(self):
        self.src = ""
        self.uuid = ""
        self.dst = ""
        self.options = ""
        self.fs_type = ""
        self.dump_p = 0
        self.fsck_p = 0


def get_fstab():
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
    lines = []
    with open("/etc/fstab", "r") as f:
        for x in f.readlines():
            if x.startswith(e.src) or (e.uuid and x.startswith("UUID=%s" % e.uuid)):
                continue
            lines.append(x)
    if not remove:
        lines.append("%s\t%s\t%s\t%s\t%i\t%i\n" % (("UUID="+e.uuid) if e.uuid else e.src, e.dst, e.fs_type, e.options, e.dump_p, e.fsck_p))
    with open("/etc/fstab", "w") as f:
        f.writelines(lines)

def get_partition_uuid_by_name(p):
    return shell("blkid -o value -s UUID " + p)["stdout"].split("\n")[0]

def get_partition_name_by_uuid(u):
    return shell("blkid -U " + u)["stdout"].split("\n")[0]
