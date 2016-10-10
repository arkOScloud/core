"""
Helper functions for managing Ruby gems.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import os
import re

from arkos import logger
from arkos.utilities import errors, shell

BINPATH = "/usr/lib/ruby/gems/2.3.0/bin"


def verify_path():
    """Verify that the proper dirs are available on the system's exec PATH."""
    profile = []
    with open("/etc/profile", "r") as f:
        for l in f.readlines():
            if l.startswith("PATH=") and BINPATH not in l:
                l = l.split('"\n')[0]
                l += ':{0}"\n'.format(BINPATH)
                profile.append(l)
                os.environ["PATH"] = os.environ["PATH"] + ":" + BINPATH
            else:
                profile.append(l)
    with open("/etc/profile", "w") as f:
        f.writelines(profile)


def install(gem, version=None, update=False):
    """
    Install a Ruby gem to the system.

    :param str gem: Gem name
    :param str version: If present, install this specific version
    :param bool update: If true, force an update
    """
    verify_path()
    if version:
        gem = gem + ":" + version
    s = shell("gem {0} -N --no-user-install {0}".format(
        "update" if update else "install", gem
    ))
    if s["code"] != 0:
        errmsg = "Gem install of {0} failed.".format(gem)
        logmsg = "Gem install failure details:\n{0}"
        logger.error("Ruby", logmsg.format(s["stderr"].decode()))
        raise errors.OperationFailedError(errmsg)


def is_installed(name):
    """
    Check if a Ruby gem is installed or not.

    :param str name: Name of package
    :returns: True if gem is installed
    :rtype: bool
    """
    if name.lower() in (x["id"].lower() for x in get_installed()):
        return True
    return False


def get_installed():
    """
    Get all installed Ruby gems.

    Returns in format `{"id": "gem_name", "version": "1.0.0"}`.
    """
    data = []
    gems = shell("gem list")["stdout"].split(b"\n")
    for x in gems:
        if not x.split():
            continue
        gem = re.search(r"^(.*) \((.*)\)$", x.decode()).group(1, 2)
        gem = {"id": gem[0], "version": gem[1]}
        data.append(gem)
    return data
