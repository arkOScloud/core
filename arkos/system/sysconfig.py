"""
Classes and functions for interacting with system management daemons.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import os

from arkos import signals
from arkos.utilities import shell


def shutdown():
    """Shutdown the system."""
    signals.emit("config", "shutdown")
    shell("shutdown -P now")


def reload():
    """Reload krakend."""
    signals.emit("config", "reload")
    shell("systemctl restart krakend")


def reboot():
    """Reboot the system."""
    signals.emit("config", "shutdown")
    shell("reboot")


def get_hostname():
    """Get system hostname."""
    with open("/etc/hostname", "r") as f:
        return f.read().rstrip("\n")


def set_hostname(name):
    """Set system hostname."""
    with open("/etc/hostname", "w") as f:
        f.write(name)
    signals.emit("config", "hn_changed", name)


def get_timezone():
    """Get current timezone. Returns ``region`` and ``zone`` in dict."""
    zone = os.path.realpath("/etc/localtime").split("/usr/share/zoneinfo/")[1]
    zone = zone.split("/")
    return {"region": zone[0], "zone": zone[1] if len(zone) > 1 else None}


def set_timezone(region, zone=None):
    """Set system timezone."""
    if zone and zone not in ["GMT", "UTC"]:
        zonepath = os.path.join("/usr/share/zoneinfo", region, zone)
    else:
        zonepath = os.path.join("/usr/share/zoneinfo", region)
    if os.path.exists("/etc/localtime"):
        os.remove("/etc/localtime")
    os.symlink(zonepath, "/etc/localtime")
    signals.emit("config", "tz_changed", (region, zone))
