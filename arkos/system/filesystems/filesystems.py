import ctypes, ctypes.util
import glob
import os
import parted
import re
import shutil

import crypto
import losetup

from arkos import config
from arkos.utilities import shell

libc = ctypes.CDLL(ctypes.util.find_library("libc"), use_errno=True)


class DiskPartition(object):
    def __init__(
            self, name="", path="", mountpoint="", size=0, geometry=2048, 
            crypt=False):
        self.name = name
        self.path = path
        self.mountpoint = mountpoint
        self.size = size
        self.geometry = geometry
        self.crypt = crypt

    def mount(self, passwd=None):
        if self.crypt and passwd:
            s = crypto.luks_open(self.path, self.name, passwd)
            if s != 0:
                raise Exception('Failed to decrypt %s with errno %s' % (self.name, str(s)))
            s = self.libc.mount(os.path.join("/dev/mapper", self.name), 
                os.path.join('/media', self.name), self.geometry, 0, None)
            if s == -1:
                crypto.luks_close(self.name)
                raise Exception('Failed to mount %s: %s' % (self.name, os.strerror(ctypes.errorno())))
        elif self.crypt and not passwd:
            raise Exception("Must provide password to decrypt encrypted disk")
        else:
            s = self.libc.mount(self.path, os.path.join('/media', self.name), self.geometry, 0, None)
            if s == -1:
                raise Exception('Failed to mount %s: %s'%(self.name, os.strerror(ctypes.errorno())))
        self.mountpoint = os.path.join('/media', self.name)
    
    def umount(self):
        if not self.mountpoint:
            return
        s = self.libc.umount2(self.mountpoint, 0)
        if s == -1:
            raise Exception('Failed to unmount %s: %s'%(self.name, os.strerror(ctypes.errorno())))
        if self.crypt:
            crypto.luks_close(self.name)
        self.remove_point_of_interest_by_path(self.mountpoint)
        self.mountpoint = ""


class VirtualDisk(object):
    def __init__(
            self, name="", path="", mountpoint="", size=0, geometry=2048,
            crypt=False):
        self.name = name
        self.path = path
        self.mountpoint = mountpoint
        self.size = size
        self.geometry = geometry
        self.crypt = crypt
    
    def create(self, mount=False):
        self.path = os.path.join(config.get("filesystems", "vdisk_dir"), self.name+'.img')
        if os.path.exists(self.path):
            raise Exception("This virtual disk already exists")
        with open(self.path, 'wb') as f:
            written = 0
            with file('/dev/zero', 'r') as zero:
                while size > written:
                    written += 1024
                    f.write(zero.read(1024))
        l = losetup.find_unused_loop_device()
        l.mount(self.path)
        s = shell('mkfs.ext4 %s' % l.device)
        if s["code"] != 0:
            raise Exception('Failed to format loop device: %s' % s["stderr"])
        l.unmount()
        if mount:
            self.mount()
    
    def mount(self, passwd=None):
        if mountpoint:
            raise Exception("Virtual disk already mounted")
        if not os.path.isdir(os.path.join('/media', self.name)):
            os.makedirs(os.path.join('/media', self.name))
        dev = losetup.find_unused_loop_device()
        dev.mount(self.path)
        p = parted.Disk(parted.getDevice(dev.device)).getPrimaryPartitions()[0]
        self.geometry = parted.probeFileSystem(p.geometry)
        if self.crypt and passwd:
            s = crypto.luks_open(dev.device, self.name, passwd)
            if s != 0:
                dev.unmount()
                raise Exception('Failed to decrypt %s with errno %s' % (self.name, str(s)))
            s = self.libc.mount(os.path.join("/dev/mapper", self.name), 
                os.path.join('/media', self.name), self.geometry, 0, None)
            if s == -1:
                crypto.luks_close(self.name)
                dev.unmount()
                raise Exception('Failed to mount %s: %s' % (self.name, os.strerror(ctypes.errorno())))
        elif self.crypt and not passwd:
            raise Exception("Must provide password to decrypt encrypted container")
        else:
            s = self.libc.mount(dev.device, os.path.join('/media', self.name), 
                self.geometry, 0, None)
            if s == -1:
                dev.unmount()
                raise Exception('Failed to mount %s: %s' % (self.name, os.strerror(ctypes.errorno())))
        self.mountpoint = os.path.join("/dev/mapper", self.name)
    
    def umount(self):
        if not self.mountpoint:
            return
        l = losetup.get_loop_devices()
        for x in l:
            if l[x].is_used() and l[x].get_filename() == self.path:
                dev = l[x]
                break
        s = self.libc.umount2(self.mountpoint, 0)
        if s == -1:
            raise Exception('Failed to unmount %s: %s'%(self.name, os.strerror(ctypes.errorno())))
        if self.crypt:
            crypto.luks_close(self.name)
        if dev:
            dev.unmount()
        self.remove_point_of_interest_by_path(self.mountpoint)
        self.mountpoint = ""
    
    def encrypt(self, passwd, cipher="aes-xts-plain64", keysize=256, mount=False):
        os.rename(self.path, os.path.join(config.get("filesystems", "vdisk_dir"), self.name+'.crypt'))
        self.path = os.path.join(config.get("filesystems", "vdisk_dir"), self.name+'.crypt')
        dev = losetup.find_unused_loop_device()
        dev.mount(self.path)
        s = crypto.luks_format(dev.device, passwd, cipher, keysize)
        if s != 0:
            if move:
                dev.unmount()
                os.rename(self.path, os.path.join(config.get("filesystems", "vdisk_dir"), self.name+'.img'))
            raise Exception('Failed to encrypt %s with errno %s'%(self.name, str(s)))
        fs["type"] = 'crypt'
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


class PointOfInterest(object):
    def __init__(self, name="", path="", stype="", icon=""):
        self.name = name
        self.path = path
        self.stype = stype
        self.icon = icon


def get_disk_partitions(name=None):
    devs, mps = [], {}
    with open("/etc/mtab", "r") as f:
        for x in f.readlines():
            x = x.split()
            mps[x[0]] = x[1]
    for d in parted.getAllDevices():
        for p in parted.Disk(d).getPrimaryPartitions():
            if path.split("/")[-1].startswith("loop"):
                continue
            dev = DiskPartition(name=p.path.split("/")[-1], path=p.path, 
                mountpoint=mps.get(p.path) or None, size=p.getSize("B"),
                geometry=parted.probeFileSystem(p.geometry), 
                crypt=crypto.is_luks(p.path))
            if name == dev.name:
                return dev
            devs.append(dev)
    return sorted(devs, key=lambda x: x.name) if not name else None

def get_virtual_disks(name=None):
    devs, mps = [], {}
    with open("/etc/mtab", "r") as f:
        for x in f.readlines():
            x = x.split()
            mps[x[0]] = x[1]
    for x in glob.glob(os.path.join(self.vdisk_dir, '*')):
        if not x.endswith((".img", ".crypt")):
            continue
        dev = VirtualDisk(name=os.path.splitext(os.path.split(x)[1])[0],
            path=x, mountpoint=mps.get(dev.path) or None, size=os.path.getsize(x),
            crypt=x.endswith(".crypt"))
        if name == dev.name:
            return dev
        vdevs.append(dev)
    return sorted(devs, key=lambda x: x.name) if not name else None

def get_points_of_interest(name=None):
    points = []
    for x in get_virtual_disks() + get_disk_partitions():
        if not x.mountpoint or (x.mountpoint == '/' or x.mountpoint.startswith('/boot')):
            continue
        if isinstance(x, VirtualDisk):
            stype = "crypt" if crypt else "vdisk"
        else:
            stype = "crypt" if crypt else "disk"
        p = PointOfInterest(name=x.name, path=x.path, stype=stype, icon="gen-storage")
        if name == p.name:
            return p
        points.append(p)
    for x in self.sites.get():
        if x.stype == 'ReverseProxy':
            continue
        p = PointOfInterest(name=x.name, path=x.path, stype="site", icon=x.icon)
        if name == p.name:
            return p
        points.append(p)
    return sorted(points, key=lambda x: x.name) if not name else None


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
