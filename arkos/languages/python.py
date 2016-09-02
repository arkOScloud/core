"""
Helper functions for managing Python packages.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos.utilities import errors, shell


def install(*mods):
    """
    Install a set of Python packages from PyPI.

    :param *mods: packages to install
    """
    mods = " ".join(x for x in mods)
    s = shell("pip install {0}".format(mods))
    if s["code"] != 0:
        raise errors.OperationFailedError(mods) from Exception(s["stderr"])


def remove(*mods):
    """
    Remove a set of Python packages from the system.

    :param *mods: packages to remove
    """
    s = shell("pip uninstall {0}".format(mods))
    if s["code"] != 0:
        raise errors.OperationFailedError(mods) from Exception(s["stderr"])


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
