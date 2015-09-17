import os

from arkos import logger
from arkos.utilities import shell

NPM_PATH = '/var/lib/npm'

def install(*mods, **kwargs):
    # Installs a set of NPM packages.
    cwd = os.getcwd()
    npm_args = " ".join(x for x in mods) + "".join(" --{0}".format(k+v if v[0]=='=' else k+" "+v) for k,v in kwargs["opts"].items())
    npm_command = _get_npm_command("install", kwargs.get("as_global", False), kwargs.get("install_path"))
    s = shell("%s%s" % (npm_command, npm_args))
    os.chdir(cwd)
    if s["code"] != 0:
        logger.error("NPM install of %s failed; log output follows:\n%s"%(" ".join(x for x in mods),s["stderr"]))
        raise Exception("NPM install failed, check logs for info")

def remove(*mods):
    # Remove an installed NPM package.
    npm_command = _get_npm_command("uninstall")
    s = shell("%s%s" % npm_command ," ".join(x for x in mods), stderr=True)
    if s["code"] != 0:
        logger.error("Failed to remove %s via npm; log output follows:\n%s"%(" ".join(x for x in mods),s["stderr"]))
        raise Exception("Failed to remove %s via npm, check logs for info"%" ".join(x for x in mods))

def install_from_package(path, stat="production", opts={}, env={}):
    # Installs a set of NPM package dependencies from an NPM package.json.
    cwd = os.getcwd()
    npm_command = _get_npm_command("install", False, path)
    npm_args = " --"+stat if stat else "" + "".join(" --{0}".format(x+"="+opts[x]) for x in opts)  
    s = shell("%s%s" % npm_command, npm_args, env)
    os.chdir(cwd)
    if s["code"] != 0:
        logger.error("NPM install of %s failed; log output follows:\n%s"%(path,s["stderr"]))
        raise Exception("NPM install failed, check logs for info")

def is_installed(name, as_global=True):
    # Returns whether NPM package is installed. 
    npm_command = _get_npm_command("ls -p --depth=0", as_global)
    s = shell("%s%s" % (npm_command, name))
    if s['code'] != 0:
        return False
    return True

def _get_npm_command(command, as_global, path=None):
    if as_global:
        return _get_global_npm_command(command)
    else:
        return _get_local_npm_command(command, path)

def _get_global_npm_command(command):
    os.chdir(NPM_PATH)
    return "sudo -u npm npm " + command + " -g "
    
def _get_local_npm_command(command, install_path):
    if install_path:
        os.chdir(install_path)
    return "npm " + command + " "
