"""
Helper functions for managing Python packages.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""


from arkos import logger
from arkos.utilities import shell


def install(*mods):
    """
    Install a set of Python packages from PyPI.

    :param *mods: packages to install
    """
    mods = " ".join(x for x in mods)
    s = shell("pip install {0}".format(mods))
    if s["code"] != 0:
        logmsg = "Failed to install {0} via PyPI; {1}"
        excmsg = "Failed to install {0} via PyPI, check logs for info"
        logger.error(logmsg.format(mods, s["stderr"]))
        raise Exception(excmsg.format(mods))


def remove(*mods):
    """
    Remove a set of Python packages from the system.

    :param *mods: packages to remove
    """
    s = shell("pip uninstall {0}".format(mods))
    if s["code"] != 0:
        logmsg = "Failed to remove {0} via PyPI; {1}"
        excmsg = "Failed to remove {0} via PyPI, check logs for info"
        logger.error(logmsg.format(mods, s["stderr"]))
        raise Exception(excmsg.format(mods))


def is_installed(name):
    """
    Check if a Python package is installed or not.

    :param str name: Name of package
    :returns: True if package is installed
    :rtype: bool
    """
    s = shell("pip freeze")
    for x in s["stdout"].split("\n"):
        if name.lower() in x.split("==")[0].lower():
            return True
    return False
