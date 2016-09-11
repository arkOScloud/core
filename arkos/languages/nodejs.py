"""
Helper functions for managing NPM packages.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import os
import re

from arkos import logger
from arkos.utilities import errors, shell

NPM_PATH = '/usr/bin'


def install(*mods, **kwargs):
    """
    Install a set of NPM packages.

    Include ``as_global`` in kwargs to install package as global.

    :param *mods: Packages to install
    :param **kwargs: Extra keyword arguments to pass to NPM
    """
    mods = " ".join(x for x in mods)
    cwd = os.getcwd()
    if "install_path" in kwargs:
        os.chdir(kwargs["install_path"])
    if kwargs is not None and "opts" in kwargs:
        mods += "".join(" --{0}".format(k+v if v[0] == '=' else k+" "+v)
                        for k, v in kwargs["opts"].items())
    npm_command = _get_npm_command("install", kwargs.get("as_global", False),
                                   kwargs.get("install_path"))
    command = "{0} {1}".format(npm_command, mods)
    s = shell(command)
    os.chdir(cwd)
    if s["code"] != 0:
        logmsg = "NPM install of {0} failed; log output follows:\n{1}"
        logger.error(logmsg.format(mods, s["stderr"]))
        raise Exception("NPM install failed, check logs for info")


def remove(*mods):
    """
    Remove a set of NPM packages.

    :param *mods: Packages to remove
    """
    mods = " ".join(x for x in mods)
    s = shell("npm uninstall {0}".format(mods), stderr=True)
    if s["code"] != 0:
        logmsg = "NPM removal of {0} failed.".format(mods)
        raise errors.OperationFailedError(logmsg) from Exception(s["stderr"])


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
        logmsg = "NPM install of {0} failed.".format(path)
        raise errors.OperationFailedError(logmsg) from Exception(s["stderr"])


def is_installed(name, as_global=True):
    """
    Return whether an NPM package is installed.

    :param str name: NPM package name
    :param bool as_global: Check global NPM instead of local
    """
    s = shell(_get_npm_command("ls -p --depth 0", as_global))
    match = re.search(str.encode(r'\b{0}\b'.format(name)), s['stdout'])
    if match:
        return True
    return False

'''
    Private commands
'''


def _get_npm_command(command, as_global, path=None):
    """ returns npm command """
    if as_global:
        return _get_global_npm_command(command)
    else:
        return _get_local_npm_command(command, path)


def _get_global_npm_command(command):
    """ returns global npm command """
    os.chdir(NPM_PATH)
    return "npm {0} -g".format(command)


def _get_local_npm_command(command, install_path):
    """ returns local npm command """
    if install_path:
        os.chdir(install_path)
    return "npm {0} ".format(command)
