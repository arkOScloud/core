import os

from arkos import logger
from arkos.utilities import shell


def install(*mods, **kwargs):
    # Installs a set of NPM packages.
    cwd = os.getcwd()
    as_global = kwargs["as_global"] if "as_global" in kwargs else True
    if "install_path" in kwargs:
        os.chdir(kwargs["install_path"])
    s = shell("npm install %s%s%s" % ("-g " if as_global else "", " ".join(x for x in mods), (" --"+" --".join(k+v if v[0]=='=' else k+" "+v for k,v in kwargs["opts"].items()) if kwargs.has_key("opts") else "")))
    os.chdir(cwd)
    if s["code"] != 0:
        logger.error("NPM install of %s failed; log output follows:\n%s"%(" ".join(x for x in mods),s["stderr"]))
        raise Exception("NPM install failed, check logs for info")

def remove(*mods):
    # Remove an installed NPM package.
    s = shell("npm uninstall %s" % " ".join(x for x in mods), stderr=True)
    if s["code"] != 0:
        logger.error("Failed to remove %s via npm; log output follows:\n%s"%(" ".join(x for x in mods),s["stderr"]))
        raise Exception("Failed to remove %s via npm, check logs for info"%" ".join(x for x in mods))

def install_from_package(path, stat="production", opts={}):
    # Installs a set of NPM package dependencies from an NPM package.json.
    cwd = os.getcwd()
    os.chdir(path)
    s = shell("npm install %s%s" % (" --"+stat if stat else "", " --"+" --".join(x+"="+opts[x] for x in opts) if opts else ""))
    os.chdir(cwd)
    if s["code"] != 0:
        logger.error("NPM install of %s failed; log output follows:\n%s"%(path,s["stderr"]))
        raise Exception("NPM install failed, check logs for info")

def is_installed(name, as_global=True):
    # Returns whether NPM package is installed. 
    s = shell("npm list -p %s%s" % ("-g " if as_global else "", name))
    if name in s['stdout']:
        return True
    return False