import ctypes, ctypes.util
import glob
import os
import parted
import re
import shutil

import crypto
import losetup

from arkos.core import Framework
from arkos.core.utilities import shell


class Filesystems(Framework):
    def on_init(self, vdisk_dir="")
        shell('modprobe loop')
        if not vdisk_dir and not self.config:
            raise Exception("No configuration values passed")
        self.vdisk_dir = vdisk_dir or self.config.get("filesystems", "vdisk_dir")
        if not os.path.exists(self.vdisk_dir):
            os.mkdir(self.vdisk_dir)
        self.libc = ctypes.CDLL(ctypes.util.find_library("libc"), use_errno=True)

    def get(self):
        devs = []
        if self.storage:
            devs = self.storage.get_list("filesystems:devs")
        if not self.storage or not devs:
            devs = self.scan_filesystems()
        if self.storage:
            self.storage.append_all("filesystems:devs", devs)
        return dictfilter(devs, kwargs)

    def get_points_of_interest(self):
        points = []
        if self.storage:
            points = self.storage.get_list("filesystems:points")
        if not self.storage or not points:
            points = self.scan_points()
        if self.storage:
            self.storage.append_all("filesystems:points", points)
        return dictfilter(points, kwargs)

    def scan_filesystems(self):
        devs, vdevs, mps = [],[],{}
        with open("/etc/mtab", "r") as f:
            for x in f.readlines():
                x = x.split()
                mps[x[0]] = x[1]
        for d in parted.getAllDevices():
            dev = {}
            dev["name"] = d.path.split("/")[-1]
            dev["dev"] = d.path
            dev["size"] = d.getSize("B")
            dev["type"] = "loop" if dev["name"].startswith("loop") else "disk"
            dev["icon"] = "gen-storage"
            dev["delete"] = False
            dev["mount"] = ""
            dev["fs"] = ""
            dev["parent"] = None
            devs.append(dev)
            for p in parted.Disk(d).getPrimaryPartitions():
                dev = {}
                dev["name"] = p.path.split("/")[-1]
                dev["dev"] = p.path
                dev["size"] = p.getSize("B")
                dev["type"] = "loop" if d.path.split("/")[-1].startswith("loop") else "part"
                dev["fs"] = parted.probeFileSystem(p.geometry)
                dev["delete"] = False
                if dev["type"] == 'part':
                    dev["icon"] = 'gen-arrow-down'
                elif dev["type"] == 'rom':
                    dev["icon"] = 'gen-cd'
                elif dev["type"] == 'crypt':
                    dev["icon"] = 'gen-lock'
                elif dev["type"] == 'loop':
                    dev["icon"] = 'gen-loop-2'
                else:
                    dev["icon"] = 'gen-storage'
                dev["mount"] = mps[p.path]
                dev["parent"] = d.path
                if dev["type"] == "loop":
                    vdevs.append(dev)
                else:
                    devs.append(dev)

        l = losetup.get_loop_devices()
        l = [l[x] for x in l if l[x].is_used()]

        for x in glob.glob(os.path.join(self.vdisk_dir, '*.img')):
            dev = {}
            found = False
            for y in l:
                if y.get_filename() == x:
                    for z in vdevs:
                        if z["dev"] == y.device:
                            found = True
                            z["name"] = os.path.splitext(os.path.split(x)[1])[0]
                            z["icon"] = 'gen-embed'
                            z["img"] = x
                            z["delete"] = True
            if not found:
                dev["name"] = os.path.splitext(os.path.split(x)[1])[0]
                dev["img"] = x
                dev["type"] = 'vdisk'
                dev["icon"] = 'gen-embed'
                dev["size"] = os.path.getsize(x)
                vdevs.append(dev)
        for x in glob.glob(os.path.join(self.vdisk_dir, '*.crypt')):
            dev = {}
            found = False
            for y in l:
                if y.get_filename() == x:
                    for z in vdevs:
                        if z["parent"] == y.device:
                            found = True
                            z["img"] = x
                            z["delete"] = True
                            vdevs.remove([i for i in vdevs if i["dev"] == z["parent"]][0])
            if not found:
                dev["name"] = os.path.splitext(os.path.split(x)[1])[0]
                dev["img"] = x
                dev["fstype"] = 'crypt'
                dev["icon"] = 'gen-lock'
                dev["size"] = os.path.getsize(x)
                vdevs.append(dev)
        devs = sorted(devs, key=lambda x: x["name"])
        vdevs = sorted(vdevs, key=lambda x: x["name"])
        return devs + vdevs

    def scan_points(self):
        points = []
        for x in self.get():
            if x["mount"] and not (x["mount"] == '/' or x["mount"].startswith('/boot')):
                points.append(x["name"], 'vdisk' if x["type"] in ["vdisk", "crypt"] else "disk", 
                    x["mount"], 'filesystems', 'gen-storage', False)
        for x in self.sites.get():
            if x["type"] != 'ReverseProxy':
                points.append(x["name"], 'website', x["path"], 'websites',
                    x["icon"], False)
        return points

    def add_vdisk(self, name, size, mkfs=True, mount=False):
        size = int(size)*1048576
        with open(os.path.join(self.vdisk_dir, name+'.img'), 'wb') as f:
            written = 0
            zero = file('/dev/zero', 'r')
            while size > written:
                written += 1024
                f.write(zero.read(1024))
            f.close()
        if mkfs:
            l = losetup.find_unused_loop_device()
            l.mount(os.path.join(self.vdisk_dir, name+'.img'))
            s = shell('mkfs.ext4 %s'%l.device)
            if s["code"] != 0:
                raise Exception('Failed to format loop device: %s'%s["stderr"])
            l.unmount()
        fs = {}
        fs["name"] = name
        fs["img"] = os.path.join(self.vdisk_dir, name+'.img')
        fs["type"] = 'vdisk'
        fs["size"] = size
        fs["parent"] = None
        fs["delete"] = True
        if mount:
            self.mount(fs)
        return fs

    def encrypt_vdisk(self, fs, passwd, cipher='aes-xts-plain64', keysize=256}, move=True, mount=False):
        opts = '-c %s -s %s -h %s'%(opts['cipher'], str(opts['keysize']), opts['hash'])
        l = losetup.get_loop_devices()
        if move:
            os.rename(os.path.join(self.vdisk_dir, fs["name"]+'.img'), os.path.join(self.vdisk_dir, fs["name"]+'.crypt'))
        dev = losetup.find_unused_loop_device()
        dev.mount(os.path.join(self.vdisk_dir, fs["name"]+'.crypt'))
        fs["img"] = os.path.join(self.vdisk_dir, fs["name"]+'.crypt')
        s = crypto.luks_format(dev["device"], passwd, cipher, keysize)
        if s != 0:
            if move:
                dev.unmount()
                os.rename(os.path.join(self.vdisk_dir, fs["name"]+'.crypt'), os.path.join(self.vdisk_dir, fs["name"]+'.img'))
            raise Exception('Failed to encrypt %s with errno %s'%(fs["name"], str(s)))
        fs["type"] = 'crypt'
        s = crypto.luks_open(dev.device, fs["name"], passwd)
        if s != 0:
            dev.unmount()
            raise Exception('Failed to decrypt %s with errno %s'%(fs["name"], str(s)))
        s = shell('mkfs.ext4 /dev/mapper/%s'%fs["name"])
        crypto.luks_close(fs["name"])
        dev.unmount()
        if s["code"] != 0:
            raise Exception('Failed to format loop device: %s'%s["stderr"])
        if mount:
            self.mount(fs, passwd)

    def mount(self, fs, passwd=''):
        if not os.path.isdir(os.path.join('/media', fs["name"])):
            os.makedirs(os.path.join('/media', fs["name"]))
        if fs["type"] in ['crypt', 'vdisk', 'loop']:
            dev = losetup.find_unused_loop_device()
            dev.mount(fs["img"])
            if fs["type"] == 'crypt':
                s = crypto.luks_open(dev.device, fs["name"], passwd)
                if s != 0:
                    dev.unmount()
                    raise Exception('Failed to decrypt %s with errno %s'%(fs["name"], str(s)))
                s = self.libc.mount(os.path.join("/dev/mapper", fs["name"]), 
                    os.path.join('/media', fs["name"]), fs["fs"], 0, None)
                if s == -1:
                    crypto.luks_close(fs["name"])
                    dev.unmount()
                    raise Exception('Failed to mount %s: %s'%(fs["name"], os.strerror(ctypes.errorno())))
            else:
                s = self.libc.mount(dev.device, os.path.join('/media', fs["name"]), 
                    fs["fs"], 0, None)
                if s == -1:
                    dev.unmount()
                    raise Exception('Failed to mount %s: %s'%(fs["name"], os.strerror(ctypes.errorno())))
            self.add_point_of_interest(fs["name"], 'vdisk', 
                fs["mount"], 'filesystems', 'gen-storage', False)
        else:
            s = self.libc.mount(fs["dev"], os.path.join('/media', fs["name"]), fs["fs"], 0, None)
            if s == -1:
                raise Exception('Failed to mount %s: %s'%(fs["name"], os.strerror(ctypes.errorno())))
            self.add_point_of_interest(fs["name"], 'disk', 
                fs["mount"], 'filesystems', 'gen-storage', False)

    def umount(self, fs, rm=False):
        if not fs["mount"]:
            return
        if fs["type"] in ['crypt', 'vdisk', 'loop']:
            dev = None
            l = losetup.get_loop_devices()
            for x in l:
                if l[x].is_used() and l[x].get_filename() == fs["img"]:
                    dev = l[x]
                    break
                s = self.libc.umount2(fs["mount"], 0)
                if s == -1:
                    raise Exception('Failed to unmount %s: %s'%(fs["name"], os.strerror(ctypes.errorno())))
                if fs["type"] == "crypt":
                    crypto.luks_close(fs["name"])
                dev.unmount()
        else:
            s = self.libc.umount2(fs["mount"], 0)
            if s == -1:
                raise Exception('Failed to unmount %s: %s'%(fs["name"], os.strerror(ctypes.errorno())))
        self.remove_point_of_interest_by_path(fs["mount"])
        if rm:
            shutil.rmtree(fs["mount"])

    def delete(self, fs):
        self.umount(fs, rm=True)
        if fs["type"] == 'crypt':
            os.unlink(os.path.join(self.vdisk_dir, fs["name"]+'.crypt'))
        else:
            os.unlink(os.path.join(self.vdisk_dir, fs["name"]+'.img'))

    def add_point_of_interest(self, name, ptype, path, by='', icon='gen-folder', remove=True):
        i = {}
        i["name"] = name
        i["type"] = ptype
        i["path"] = path
        i["icon"] = icon
        i["created_by"] = by
        i["remove"] = remove
        if self.storage:
            self.storage.append("filesystems:points", i)

    def remove_point_of_interest(self, i):
        if self.storage:
            self.storage.remove("filesystems:points", i)

    def remove_point_of_interest_by_path(self, path):
        if self.storage:
            self.storage.remove(self.get_points_of_interest(path=path))


class Entry:
    def __init__(self):
        self.src = ''
        self.dst = ''
        self.options = ''
        self.fs_type = ''
        self.dump_p = 0
        self.fsck_p = 0


def read():
    ss = ConfManager.get().load('filesystems', '/etc/fstab').split('\n')
    r = []

    for s in ss:
        if s != '' and s[0] != '#':
            try:
                s = s.split()
                e = Entry()
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

def save(ee):
    d = ''
    for e in ee:
        d += '%s\t%s\t%s\t%s\t%i\t%i\n' % (e.src, e.dst, e.fs_type, e.options, e.dump_p, e.fsck_p)
    ConfManager.get().save('filesystems', '/etc/fstab', d)
    ConfManager.get().commit('filesystems')

def list_disks():
    r = []
    for s in os.listdir('/dev'):
        if re.match('sd.$|hd.$|scd.$|fd.$|ad.+$', s):
            r.append('/dev/' + s)
    return sorted(r)

def list_partitions():
    r = []
    for s in os.listdir('/dev'):
        if re.match('sd..$|hd..$|scd.$|fd.$', s):
            r.append('/dev/' + s)
    return sorted(r)

def get_disk_vendor(d):
    return ' '.join(shell('hdparm -I ' + d + ' | grep Model')["stdout"].split()[3:])

def get_partition_uuid_by_name(p):
    return shell('blkid -o value -s UUID ' + p)["stdout"].split('\n')[0]

def get_partition_name_by_uuid(u):
    return shell('blkid -U ' + u)["stdout"]
