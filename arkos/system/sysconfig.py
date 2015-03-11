import os

from arkos.utilities import shell


def shutdown():
    shell('shutdown -P now')

def reboot():
    shell('reboot')

def get_hostname():
    with open('/etc/hostname', 'r') as f:
        return f.read().rstrip("\n")

def set_hostname(name):
    with open('/etc/hostname', 'w') as f:
        f.write(name)

def get_timezone():
    zone = os.path.realpath('/etc/localtime').split('/usr/share/zoneinfo/')[1]
    zone = zone.split("/")
    return {"region": zone[0], "zone": zone[1] if len(zone) > 1 else None}

def set_timezone(region, zone=None):
    if zone and not zone in ["GMT", "UTC"]:
        zonepath = os.path.join('/usr/share/zoneinfo', region, zone)
    else:
        zonepath = os.path.join('/usr/share/zoneinfo', region)
    if os.path.exists('/etc/localtime'):
        os.remove('/etc/localtime')
    os.symlink(zonepath, '/etc/localtime')
