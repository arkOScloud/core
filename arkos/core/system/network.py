import fcntl
import netifaces
import psutil
import socket
import struct
import sys

from arkos.core.utilities import shell


def get_connections(self):
    conns = []
    netctl = shell('netctl list')
    for line in netctl["stdout"].split('\n'):
        if not line.split():
            continue
        d = {"name": line[2:], "status": line.startswith('*')}
        with open(os.path.join('/etc/netctl', line), "r") as f:
            data = f.readlines()
        for x in data:
            if x.startswith('#') or not x.strip():
                continue
            parse = x.split('=')
            d[parse[0]] = parse[1].translate(None, '()\"\'\n')
        d["enabled"] = os.path.exists('/etc/systemd/system/multi-user.target.wants/netctl@' + d["name"] + '.service')
        conns.append(d)
    return conns

def get_interfaces(self):
    ifaces = []
    for x in netifaces.interfaces():
        rx, tx = self.get_rxtx(x)
        data = {"name": x, "class": self.detect_dev_class(x), 
        "ip": self.get_ip(x), "rx": rx, "tx": tx, "up": self.is_up(x)}
        ifaces.append(data)
    return ifaces

def get_rxtx(self, iface):
    data = psutil.net_io_counters(pernic=True)
    data = data[iface] if type(data) == dict else data
    return (data[0], data[1])
    
def get_ip(self, iface, v6=False):
    s = netifaces.ifaddresses(iface)
    s = (s[netifaces.AF_INET6] + s[netifaces.AF_INET]) if v6 else s[netifaces.AF_INET]
    return s

def get_active_ranges(self):
    ranges = []
    for x in self.get_interfaces():
        for y in x["ip"]:
            if '127.0.0.1' in y or '0.0.0.0' in y:
                continue
            if not '/' in y:
                ri = y
                rr = '32'
            else:
                ri, rr = y.split('/')
            ri = ri.split('.')
            ri[3] = '0'
            ri = ".".join(ri)
            y = ri + '/' + rr
            ranges.append(y)
    return ranges

def is_interface_up(self, iface):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        r = fcntl.ioctl(s.fileno(), 0x8913, iface + ("\0"*256))
    flags, = struct.unpack("H", r[16:18])
    up = flags & 1
    return up == 1

def detect_dev_class(self, iface):
    if iface.name[:-1] in ['ppp', 'wvdial']:
        return 'ppp'
    elif iface.name[:2] in ['wl', 'ra', 'wi', 'at']:
        return 'wireless'
    elif iface.name[:2].lower() == 'br':
        return 'bridge'
    elif iface.name[:2].lower() == 'tu':
        return 'tunnel'
    elif iface.name.lower() == 'lo':
        return 'loopback'
    elif iface.name[:2] in ["et", "en"]:
        return 'ethernet'
    return 'Unknown'

def connect(self, conn):
    shell('netctl start %s' % c["name"])

def disconnect(self, conn):
    shell('netctl stop %s' % c["name"])

def enable(self, conn):
    shell('netctl enable %s' % c["name"])

def disable(self, conn):
    shell('netctl disable %s' % c["name"])

def iface_up(self, iface):
    shell('ip link set dev %s up' % iface.name)

def iface_down(self, iface):
    shell('ip link set dev %s down' % iface.name)

def iface_enable(self, iface):
    shell('systemctl enable netctl-auto@%s.service' % iface.name)

def iface_disable(self, iface):
    shell('systemctl disable netctl-auto@%s.service' % iface.name)
