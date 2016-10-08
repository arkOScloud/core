"""
Helper functions for managing Python packages.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos import logger
from arkos.utilities import errors, shell


def install(pkg, version=None, py2=False):
    """
    Install a set of Python packages from PyPI.

    :param str pkg: package to install
    :param str version: If present, install this specific version
    :param bool py2: If True, install for Python 2.x instead
    """
    if version:
        pkg = pkg + "==" + version
    s = shell("pip{0} install {1}".format("2" if py2 else "", pkg))
    if s["code"] != 0:
        errmsg = "PyPI install of {0} failed.".format(pkg)
        logmsg = "PyPI install failure details:\n{0}"
        logger.error("Python", logmsg.format(s["stderr"].decode()))
        raise errors.OperationFailedError(errmsg)


def remove(*mods):
    """
    Remove a set of Python packages from the system.

    :param *mods: packages to remove
    """
    s = shell("pip uninstall {0}".format(mods))
    if s["code"] != 0:
        errmsg = "PyPI uninstall of {0} failed.".format(mods)
        logmsg = "PyPI uninstall failure details:\n{0}"
        logger.error("Python", logmsg.format(s["stderr"].decode()))
        raise errors.OperationFailedError(errmsg)


def is_installed(name):
    """
    Check if a Python package is installed or not.

    :param str name: Name of package
    :returns: True if package is installed
    :rtype: bool
    """
    if name.lower() in (x["id"].lower() for x in get_installed()):
        return True
    return False


def get_installed():
    """
    Get all installed Python packages.

    Returns in format `{"id": "package_name", "version": "1.0.0"}`.
    """
    s = shell("pip freeze")
    return [
        {"id": x.split(b"==")[0], "version": x.split(b"==")[1]}
        for x in s["stdout"].split(b"\n") if x.split() and b"==" in x
    ]
