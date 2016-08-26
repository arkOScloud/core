"""
Helper functions for managing Composer packages and PHP modules.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import os
import re
import requests

from distutils.spawn import find_executable

from arkos.utilities import shell


def install_composer():
    """Install Composer to the system."""
    cwd = os.getcwd()
    os.chdir("/root")
    os.environ["COMPOSER_HOME"] = "/root"
    enable_mod("phar")
    open_basedir("add", "/root")
    r = requests.get("https://getcomposer.org/installer")
    s = shell("php", stdin=r.text)
    os.chdir(cwd)
    if s["code"] != 0:
        excmsg = "Composer download/config failed. Error: {0}"
        raise Exception(excmsg.format(str(s["stderr"])))
    os.rename("/root/composer.phar", "/usr/local/bin/composer")
    os.chmod("/usr/local/bin/composer", 0o755)
    open_basedir("add", "/usr/local/bin")


def verify_composer():
    """Verify Composer installation status."""
    if not find_executable("composer"):
        install_composer()
    if not find_executable("composer"):
        raise Exception("Composer was not installed successfully.")


def composer_install(path):
    """
    Install a PHP application bundle via Composer.

    :param str path: path to app directory
    """
    verify_composer()
    cwd = os.getcwd()
    os.chdir(path)
    shell("composer self-update")
    s = shell("composer install")
    os.chdir(cwd)
    if s["code"] != 0:
        excmsg = "Composer failed to install this app's bundle. Error: {0}"
        raise Exception(excmsg.format(str(s["stderr"])))


def change_setting(name, value, config_file="/etc/php/php.ini"):
    """
    Change a key value in php.ini.

    :param str name: key of setting to change
    :param str value: key value to set
    :param str config_file: Config file to edit
    """
    with open(config_file, "r") as f:
        lines = f.readlines()
    with open(config_file, "w") as f:
        matched = False
        for line in lines:
            if re.search(re.escape(name) + "\s*=", line):
                line = name+" = "+value+"\n"
                matched = True
            f.write(line)
        if not matched:
            f.write(name+" = "+value+"\n")


def enable_mod(*args, **kwargs):
    """
    Enable a PHP extension in php.ini.

    Include ``config_file`` in kwargs to edit a file that is not "php.ini".

    :param *args: mods to enable
    """
    config_file = kwargs.get("config_file", "/etc/php/php.ini")
    with open(config_file, "r") as f:
        lines = f.readlines()
    with open(config_file, "w") as f:
        for line in lines:
            for x in args:
                if ";extension={0}.so".format(x) in line:
                    line = "extension={0}.so\n".format(x)
                if ";zend_extension={0}.so".format(x) in line:
                    line = "zend_extension={0}.so\n".format(x)
            f.write(line)


def disable_mod(*mod, **kwargs):
    """
    Disable a PHP extension in php.ini.

    Include ``config_file`` in kwargs to edit a file that is not "php.ini".

    :param *args: mods to enable
    """
    config_file = kwargs.get("config_file", "/etc/php/php.ini")
    with open(config_file, "r") as f:
        lines = f.readlines()
    with open(config_file, "w") as f:
        for line in lines:
            for x in mod:
                sw = line.startswith(";")
                if "extension={0}.so".format(x) in line and not sw:
                    line = ";extension={0}.so\n".format(x)
            f.write(line)


def open_basedir(op, path):
    """
    Add or remove a path to php.ini's open_basedir setting.

    :param str op: "add" or "del"
    :param str path: path to add or remove from open_basedir
    """
    oc = []
    with open("/etc/php/php.ini", "r") as f:
        ic = f.readlines()
    if op == "del":
        for l in ic:
            if "open_basedir = " in l and path in l:
                l = l.replace(":"+path, "")
                l = l.replace(":"+path+"/", "")
                oc.append(l)
            else:
                oc.append(l)
    else:
        for l in ic:
            if "open_basedir = " in l and path not in l:
                l = l.rstrip("\n") + ":{0}\n".format(path)
                if l.startswith(";open_basedir"):
                    l = l.replace(";open_basedir", "open_basedir")
                oc.append(l)
            else:
                oc.append(l)
    with open("/etc/php/php.ini", "w") as f:
        f.writelines(oc)


def upload_size(size):
    """
    Set PHP's max upload and post sizes.

    :param int size: Size to set (in MB)
    """
    oc = []
    with open("/etc/php/php.ini", "r") as f:
        ic = f.readlines()
    for l in ic:
        if "upload_max_filesize = " in l:
            l = "upload_max_filesize = {0}M".format(size)
        elif "post_max_size = " in l:
            l = "post_max_size = {0}M".format(size)
        oc.append(l)
    with open("/etc/php/php.ini", "w") as f:
        f.writelines(oc)
