"""
Helper functions for managing NPM packages.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import os

from arkos import logger
from arkos.utilities import errors, shell


def install(*mods, **kwargs):
    """
    Install a set of NPM packages.

    Include ``as_global`` in kwargs to install package as global.

    :param *mods: Packages to install
    :param **kwargs: Extra keyword arguments to pass to NPM
    """
    as_global = "-g " if kwargs.get("as_global") else ""
    mods = " ".join(x for x in mods)
    opt_str = ""
    if kwargs.get("opts"):
        opt_str += " --"
    for k, v in kwargs.get("opts", {}):
        opt_str += " --".join(k+v if v[0] == '=' else k+" "+v)
    cwd = os.getcwd()
    if "install_path" in kwargs:
        os.chdir(kwargs["install_path"])
    s = shell("npm install {0}{1}{2}".format(as_global, mods, ))
    os.chdir(cwd)
    if s["code"] != 0:
        errmsg = "NPM install of {0} failed.".format(mods)
        logmsg = "NPM install failure details:\n{0}"
        logger.error("NodeJS", logmsg.format(s["stderr"].decode()))
        raise errors.OperationFailedError(errmsg)


def remove(*mods):
    """
    Remove a set of NPM packages.

    :param *mods: Packages to remove
    """
    mods = " ".join(x for x in mods)
    s = shell("npm uninstall {0}".format(mods), stderr=True)
    if s["code"] != 0:
        errmsg = "NPM removal of {0} failed.".format(mods)
        logmsg = "NPM remove failure details:\n{0}"
        logger.error("NodeJS", logmsg.format(s["stderr"].decode()))
        raise errors.OperationFailedError(errmsg)


def install_from_package(path, stat="production", opts={}):
    """
    Install a set of NPM package dependencies from an NPM package.json.

    :param str path: path to directory with package.json
    :param str stat: Install to "production"?
    """
    stat = (" --"+stat) if stat else ""
    opts = (" --"+" --".join(x+"="+y for x, y in opts)) if opts else ""
    cwd = os.getcwd()
    os.chdir(path)
    s = shell("npm install {0}{1}".format(stat, opts))
    os.chdir(cwd)
    if s["code"] != 0:
        errmsg = "NPM install of {0} failed.".format(path)
        logmsg = "NPM install failure details:\n{0}"
        logger.error("NodeJS", logmsg.format(s["stderr"].decode()))
        raise errors.OperationFailedError(errmsg)


def is_installed(name, as_global=True):
    """
    Return whether an NPM package is installed.

    :param str name: NPM package name
    :param bool as_global: Check global NPM instead of local
    """
    s = shell("npm list -p {0}{1}".format("-g " if as_global else "", name))
    if name in s['stdout']:
        return True
    return False
