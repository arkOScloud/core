import os
import re
import urllib2

from distutils.spawn import find_executable

from arkos.utilities import shell


def install_composer():
    # Installs Composer to the system.
    cwd = os.getcwd()
    os.chdir("/root")
    os.environ["COMPOSER_HOME"] = "/root"
    enable_mod("phar")
    open_basedir("add", "/root")
    installer = urllib2.urlopen("https://getcomposer.org/installer").read()
    s = shell("php", stdin=installer)
    os.chdir(cwd)
    if s["code"] != 0:
        raise Exception("Composer download/config failed. Error: %s"%str(s["stderr"]))
    os.rename("/root/composer.phar", "/usr/local/bin/composer")
    os.chmod("/usr/local/bin/composer", 755)
    open_basedir("add", "/usr/local/bin")

def verify_composer():
    if not find_executable("composer"):
        install_composer()
    if not find_executable("composer"):
        raise Exception("Composer was not installed successfully.")

def composer_install(path):
    # Install a PHP application bundle via Composer.
    verify_composer()
    cwd = os.getcwd()
    os.chdir(path)
    shell("composer self-update")
    s = shell("composer install")
    os.chdir(cwd)
    if s["code"] != 0:
        raise Exception("Composer failed to install this app's bundle. Error: %s"%str(s["stderr"]))

def change_setting(name, value):
    # Change a key value in php.ini
    with open("/etc/php/php.ini", "r") as f:
        lines = f.readlines()
    with open("/etc/php/php.ini", "w") as f:
        for line in lines:
            if name+" = " in line:
                line = name+" = "+value+"\n"
            f.write(line)

def enable_mod(*mod):
    # Enable a PHP extension in php.ini
    with open("/etc/php/php.ini", "r") as f:
        lines = f.readlines()
    with open("/etc/php/php.ini", "w") as f:
        for line in lines:
            for x in mod:
                if ";extension=%s.so"%x in line:
                    line = "extension=%s.so\n"%x
            f.write(line)

def disable_mod(*mod):
    # Enable a PHP extension in php.ini
    with open("/etc/php/php.ini", "r") as f:
        lines = f.readlines()
    with open("/etc/php/php.ini", "w") as f:
        for line in lines:
            for x in mod:
                if "extension=%s.so"%x in line and not line.startswith(";"):
                    line = ";extension=%s.so\n"%x
            f.write(line)

def open_basedir(op, path):
    # Add or remove a path to php.ini's open_basedir setting.
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
                l = l.rstrip("\n") + ":%s\n" % path
                oc.append(l)
            else:
                oc.append(l)
    with open("/etc/php/php.ini", "w") as f:
        f.writelines(oc)

def upload_size(size):
    # Set PHP's max upload and post sizes.
    oc = []
    with open("/etc/php/php.ini", "r") as f:
        ic = f.readlines()
    for l in ic:
        if "upload_max_filesize = " in l:
            l = "upload_max_filesize = %sM" % size
        elif "post_max_size = " in l:
            l = "post_max_size = %sM" % size
        oc.append(l)
    with open("/etc/php/php.ini", "w") as f:
        f.writelines(oc)
