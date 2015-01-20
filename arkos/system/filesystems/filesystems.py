import ctypes, ctypes.util
import glob
import os
import parted
import re
import shutil

import crypto
import losetup

from arkos import config, storage
from arkos.utilities import shell

libc = ctypes.CDLL(ctypes.util.find_library("libc"), use_errno=True)


class DiskPartition(object):
    def __init__(
            self, name="", path="", mountpoint="", size=0, fstype="", 
            crypt=False):
        self.name = name
        self.path = path
        self.mountpoint = mountpoint
        self.size = size
        self.fstype = fstype
        self.crypt = crypt

    def mount(self, passwd=None):
        if self.mountpoint and os.path.ismount(self.mountpoint):
            raise Exception("Disk partition already mounted")
        mount_point = self.mountpoint if self.mountpoint else os.path.join('/media', self.name)
        if self.crypt and passwd:
            s = crypto.luks_open(self.path, self.name, passwd)
            if s != 0:
                raise Exception('Failed to decrypt %s with errno %s' % (self.name, str(s)))
            s = libc.mount(ctypes.c_char_p(os.path.join("/dev/mapper", self.name)), 
                ctypes.c_char_p(mount_point), 
                ctypes.c_char_p(self.fstype), 0, ctypes.c_char_p(""))
            if s == -1:
                crypto.luks_close(self.name)
                raise Exception('Failed to mount %s: %s' % (self.name, os.strerror(ctypes.get_errno())))
        elif self.crypt and not passwd:
            raise Exception("Must provide password to decrypt encrypted disk")
        else:
            s = libc.mount(ctypes.c_char_p(self.path), 
                ctypes.c_char_p(mount_point), 
                ctypes.c_char_p(self.fstype), 0, ctypes.c_char_p(""))
            if s == -1:
                raise Exception('Failed to mount %s: %s'%(self.name, os.strerror(ctypes.get_errno())))
        self.mountpoint = mount_point
        register_point(self.name, self.mountpoint, "crypt" if self.crypt else "disk")
    
    def umount(self):
        if not self.mountpoint:
            return
        s = libc.umount2(ctypes.c_char_p(self.mountpoint), 0)
        if s == -1:
            raise Exception('Failed to unmount %s: %s'%(self.name, os.strerror(ctypes.get_errno())))
        if self.crypt:
            crypto.luks_close(self.name)
        deregister_point(self.name)
        self.mountpoint = ""
    
    def as_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "mountpoint": self.mountpoint,
            "size": self.size,
            "fstype": self.fstype,
            "crypt": self.crypt
        }


class VirtualDisk(object):
    def __init__(
            self, name="", path="", mountpoint="", size=0, fstype="ext4",
            crypt=False):
        self.name = name
        self.path = path
        self.mountpoint = mountpoint
        self.size = size
        self.fstype = fstype
        self.crypt = crypt
    
    def create(self, mount=False):
        self.path = str(os.path.join(config.get("filesystems", "vdisk_dir"), self.name+'.img'))
        if os.path.exists(self.path):
            raise Exception("This virtual disk already exists")
        with open(self.path, 'wb') as f:
            written = 0
            with file('/dev/zero', 'r') as zero:
                while self.size > written:
                    written += 1024
                    f.write(zero.read(1024))
        l = losetup.find_unused_loop_device()
        l.mount(str(self.path))
        s = shell('mkfs.ext4 %s' % l.device)
        if s["code"] != 0:
            raise Exception('Failed to format loop device: %s' % s["stderr"])
        l.unmount()
        if mount:
            self.mount()
    
    def mount(self, passwd=None):
        if self.mountpoint and os.path.ismount(self.mountpoint):
            raise Exception("Virtual disk already mounted")
        if not os.path.isdir(os.path.join('/media', self.name)):
            os.makedirs(os.path.join('/media', self.name))
        mount_point = self.mountpoint if self.mountpoint else os.path.join('/media', self.name)
        dev = losetup.find_unused_loop_device()
        dev.mount(str(self.path), offset=1048576)
        if self.crypt and passwd:
            s = crypto.luks_open(dev.device, self.name, passwd)
            if s != 0:
                dev.unmount()
                raise Exception('Failed to decrypt %s with errno %s' % (self.name, str(s)))
            s = libc.mount(ctypes.c_char_p(os.path.join("/dev/mapper", self.name)), 
                ctypes.c_char_p(mount_point), 
                ctypes.c_char_p(self.fstype), 0, ctypes.c_char_p(""))
            if s == -1:
                crypto.luks_close(self.name)
                dev.unmount()
                raise Exception('Failed to mount %s: %s' % (self.name, os.strerror(ctypes.get_errno())))
        elif self.crypt and not passwd:
            raise Exception("Must provide password to decrypt encrypted container")
        else:
            s = libc.mount(ctypes.c_char_p(dev.device), ctypes.c_char_p(mount_point), 
                ctypes.c_char_p(self.fstype), 0, ctypes.c_char_p(""))
            if s == -1:
                dev.unmount()
                raise Exception('Failed to mount %s: %s' % (self.name, os.strerror(ctypes.get_errno())))
        self.mountpoint = mount_point
        register_point(self.name, self.mountpoint, "crypt" if self.crypt else "vdisk")
    
    def umount(self):
        if not self.mountpoint:
            return
        l = losetup.get_loop_devices()
        for x in l:
            if l[x].is_used() and l[x].get_filename() == self.path:
                dev = l[x]
                break
        s = libc.umount2(ctypes.c_char_p(self.mountpoint), 0)
        if s == -1:
            raise Exception('Failed to unmount %s: %s'%(self.name, os.strerror(ctypes.get_errno())))
        if self.crypt:
            crypto.luks_close(self.name)
        if dev:
            dev.unmount()
        deregister_point(self.name)
        self.mountpoint = ""
    
    def encrypt(self, passwd, cipher="aes-xts-plain64", keysize=256, mount=False):
        os.rename(self.path, os.path.join(config.get("filesystems", "vdisk_dir"), self.name+'.crypt'))
        self.path = os.path.join(config.get("filesystems", "vdisk_dir"), self.name+'.crypt')
        dev = losetup.find_unused_loop_device()
        dev.mount(str(self.path), offset=1048576)
        s = crypto.luks_format(dev.device, passwd, cipher, keysize)
        if s != 0:
            dev.unmount()
            os.rename(self.path, os.path.join(config.get("filesystems", "vdisk_dir"), self.name+'.img'))
            raise Exception('Failed to encrypt %s with errno %s'%(self.name, str(s)))
        s = crypto.luks_open(dev.device, self.name, passwd)
        if s != 0:
            dev.unmount()
            raise Exception('Failed to decrypt %s with errno %s'%(self.name, str(s)))
        s = shell('mkfs.ext4 /dev/mapper/%s' % self.name)
        crypto.luks_close(self.name)
        dev.unmount()
        if s["code"] != 0:
            raise Exception('Failed to format loop device: %s' % s["stderr"])
        self.crypt = True
        if mount:
            self.mount(passwd)
    
    def remove(self):
        self.umount()
        os.unlink(self.path)
    
    def as_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "mountpoint": self.mountpoint,
            "size": self.size,
            "fstype": self.fstype,
            "crypt": self.crypt
        }


class PointOfInterest(object):
    def __init__(self, name="", path="", stype="", icon=""):
        self.name = name
        self.path = path
        self.stype = stype
        self.icon = icon
    
    def add(self):
        deregister_point(path=self.path)
        storage.points.add("points", self)
    
    def remove(self):
        storage.points.remove("points", self)
    
    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.stype,
            "icon": self.icon
        }


def get_disk_partitions(name=None):
    devs, mps = [], {}
    with open("/etc/mtab", "r") as f:
        for x in f.readlines():
            x = x.split()
            mps[x[0]] = x[1]
    for d in parted.getAllDevices():
        try:
            parts = parted.Disk(d).getPrimaryPartitions()
        except:
            continue
        for p in parts:
            if p.path.split("/")[-1].startswith("loop"):
                continue
            dev = DiskPartition(name=p.path.split("/")[-1], path=p.path, 
                mountpoint=mps.get(p.path) or None, size=p.getSize("B"),
                fstype=parted.probeFileSystem(p.geometry), crypt=crypto.is_luks(p.path)==0)
            if dev.mountpoint and not get_points(path=dev.mountpoint):
                register_point(dev.name, dev.mountpoint, "crypt" if dev.crypt else "disk")
            if name == dev.name:
                return dev
            devs.append(dev)
    return devs if not name else None

def get_virtual_disks(name=None):
    devs, mps = [], {}
    with open("/etc/mtab", "r") as f:
        for x in f.readlines():
            x = x.split()
            mps[x[0]] = x[1]
    for x in losetup.get_loop_devices():
        try:
            s = x.get_status()
        except:
            continue
        if "/dev/loop%s" % s.lo_number in mps:
            mps[s.lo_filename] = mps["/dev/loop%s" % s.lo_number]
    for x in glob.glob(os.path.join(config.get("filesystems", "vdisk_dir"), '*')):
        if not x.endswith((".img", ".crypt")):
            continue
        dname = os.path.splitext(os.path.split(x)[1])[0]
        dev = VirtualDisk(name=dname, path=x, size=os.path.getsize(x),
            mountpoint=mps.get(x) or mps.get("/dev/mapper/%s" % dname) or None, 
            crypt=x.endswith(".crypt"))
        if dev.mountpoint and not get_points(path=dev.mountpoint):
            register_point(dev.name, dev.mountpoint, "crypt" if dev.crypt else "disk")
        if name == dev.name:
            return dev
        devs.append(dev)
    return devs if not name else None

def get_points(id=None, path=None):
    points = storage.points.get("points")
    if id:
        for x in points:
            if x.name == id:
                return x
    elif path:
        for x in points:
            if x.path == path:
                return x
    return points

def register_point(name, path, stype, icon="gen-storage"):
    p = PointOfInterest(name, path, stype, icon)
    p.add()

def deregister_point(id=None, path=None):
    p = get_points(id=id, path=path)
    if (id or path) and p: p.remove()


class FstabEntry:
    def __init__(self):
        self.src = ''
        self.dst = ''
        self.options = ''
        self.fs_type = ''
        self.dump_p = 0
        self.fsck_p = 0


def get_fstab():
    r = []
    with open("/etc/fstab", "r") as f:
        ss = f.readlines()

    for s in ss:
        if s != '' and s[0] != '#':
            try:
                s = s.split()
                e = FstabEntry()
                try:
                    e.src = s[0]
                    e.dst = s[1]
                    e.fs_type = s[2]
                    e.options = s[3]
                    e.dump_p = int(s[4])
                    e.fsck_p = int(s[5])
                except:
                    pass
                r.append(e)
            except:
                pass
    return r

def save_fstab_entry(e):
    lines = []
    with open("/etc/fstab", "r") as f:
        for x in f.readlines():
            if x.startswith(e.src):
                continue
            lines.append(x)
    lines.append('%s\t%s\t%s\t%s\t%i\t%i\n' % (e.src, e.dst, e.fs_type, e.options, e.dump_p, e.fsck_p))
    with open("/etc/fstab", "w") as f:
        f.write(d)

def get_partition_uuid_by_name(p):
    return shell('blkid -o value -s UUID ' + p)["stdout"].split('\n')[0]

def get_partition_name_by_uuid(u):
    return shell('blkid -U ' + u)["stdout"]
