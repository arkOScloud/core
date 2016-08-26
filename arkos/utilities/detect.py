"""
Helper functions to detect system architecture and platform.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import platform

EMPTY_STRING = ""


def detect_architecture():
    """Detect system architecture and board type."""
    btype = "Unknown"
    cpuinfo = {}
    # Get architecture
    arch = platform.machine()
    # Let's play a guessing game!
    if arch in ["x86_64", "i386", "i686"]:
        btype = "General"
    else:
        with open("/proc/cpuinfo", "r") as f:
            d = f.read().split("\n")
        for x in d:
            # Parse output of function c_show in linux/arch/arm/kernel/setup.c
            k, _, v = x.partition(":")
            cpuinfo[k.strip()] = v.strip()
        # Is this a... Raspberry Pi?
        if cpuinfo.get("Hardware", "") in ("BCM2708", "BCM2835"):
            btype = "Raspberry Pi"
        elif cpuinfo.get("Hardware", "") in ("BCM2709", "BCM2836")\
                and "crc32" not in cpuinfo["Features"]:
            btype = "Raspberry Pi 2"
        elif cpuinfo.get("Hardware", "") in ("BCM2709", "BCM2710", "BCM2837")\
                and "crc32" in cpuinfo["Features"]:
            arch = "aarch64"
            btype = "Raspberry Pi 3"
        # Is this a... BeagleBone Black?
        elif "Hardware" in cpuinfo and "Generic AM33XX" in cpuinfo["Hardware"]\
                and cpuinfo["CPU part"] == "0xc08":
            btype = "BeagleBone Black"
        # Is this a Cubieboard (series)?
        elif cpuinfo.get("Hardware", "") == "sun7i"\
                and cpuinfo["CPU part"] == "0xc07":
            meminfo = {}
            # Since both the Cubieboard2 and Cubietruck have the same processor
            # we need to check memory size to make a good guess.
            with open("/proc/meminfo", "r") as f:
                d = f.read().split("\n")
            for x in d:
                k, _, v = x.partition(":")
                meminfo[k.strip()] = v.strip()
            # Is this a... Cubieboard2?
            if int(meminfo["MemTotal"].split(" ")[0]) < 1100000:
                btype = "Cubieboard2"
            # Then it must be a Cubietruck!
            else:
                btype = "Cubietruck"
    return (arch, btype)


def detect_platform(mapping=True):
    """Detect distro platform."""
    base_mapping = {
        "gentoo base system": "gentoo",
        "centos linux": "centos",
        "mandriva linux": "mandriva",
    }

    platform_mapping = {
        "ubuntu": "debian",
        "linuxmint": "debian",
        "manjaro": "arch",
        "antergos": "arch",
        "bluestar": "arch",
        "archbang": "arch"
    }

    if platform.system() != "Linux":
        return platform.system().lower()

    dist = ""
    (major, minor, _) = platform.python_version_tuple()
    if (int(major) * 10 + int(minor)) >= 26:
        dist = platform.linux_distribution()[0]
    else:
        dist = platform.dist()[0]

    if dist == "":
        try:
            with open("/etc/issue", "r") as f:
                dist = f.read().split()[0]
        except:
            dist = "unknown"

    res = dist.strip().lower()
    if res in base_mapping:
        res = base_mapping[res]
    if mapping and res in platform_mapping:
        res = platform_mapping[res]
    return res
