# coding: utf-8
"""
Helper functions for obtaining system statistics.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import datetime
import os
import psutil

from arkos import config


def get_all():
    """Get all available statistics."""
    return {
        "load": get_load(),
        "temp": get_temp(),
        "ram": get_ram(),
        "cpu": get_cpu(),
        "swap": get_swap(),
        "disks": get_space(),
        "uptime": get_uptime()
    }


def get_load():
    """Get system load averages."""
    return os.getloadavg()


def get_temp():
    """Get CPU temperature readings."""
    # TODO: replace this with libsensors.so / PySensors
    if config.get("enviro", "board", "Unknown").startswith("Raspberry Pi"):
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return "{:3.1f}°C".format(float(f.read().rstrip("\n"))/1000)
    else:
        if os.path.exists("/sys/class/hwmon/hwmon1/temp1_input"):
            with open("/sys/class/hwmon/hwmon1/temp1_input", "r") as f:
                return "{:3.1}f°C".format(float(f.read().rstrip("\n"))/1000)
    return ""


def get_ram():
    """Get free and total RAM stats."""
    s = psutil.virtual_memory()
    return (int(s.available), int(s.total), int(s.percent))


def get_cpu():
    """Get current CPU use percentage."""
    return psutil.cpu_percent(interval=1)


def get_swap():
    """Get current swap space usage."""
    s = psutil.swap_memory()
    return (int(s.used), int(s.total))


def get_space():
    """Get used disk space."""
    result = []
    for x in psutil.disk_partitions():
        r = psutil.disk_usage(x.mountpoint)
        did = x.mountpoint.split("/")[-1] if "/loop" in x.device else x.device
        result.append({"id": did , "used": r.used, "total": r.total,
                       "percent": r.percent})
    return result


def get_uptime():
    """Get system uptime."""
    n = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
    m, s = divmod(n.seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    return [s, m, h, n.days]
