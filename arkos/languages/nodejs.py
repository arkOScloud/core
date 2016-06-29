import os, re, shlex

from arkos import logger
from arkos.utilities import shell

NPM_PATH = '/var/lib/npm'

def install(*mods, **kwargs):
    # Installs a set of NPM packages.
    cwd = os.getcwd()
    npm_args = " ".join(x for x in mods) 
    if kwargs is not None and kwargs["opts"] is not None: 
        npm_args += "".join(" --{0}".format(k+v if v[0]=='=' else k+" "+v) for k,v in kwargs["opts"].viewitems())
    npm_command = _get_npm_command("install", kwargs.get("as_global", False), kwargs.get("install_path"))
    s = shell("%s%s" % (npm_command, npm_args))
    os.chdir(cwd)
    if s["code"] != 0:
        logger.error("NPM install of %s failed; log output follows:\n%s"%(" ".join(x for x in mods),s["stderr"]))
        raise Exception("NPM install failed, check logs for info")

def remove(*mods):
    # Removes an installed NPM package.
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
    s = shell(_get_npm_command("ls -p --depth 0", as_global))
    match = re.search(r'\b%s\b' % (name), s['stdout'])
    if match:
        return True
    return False

def has_user(user):
    # Checks if user exists in npm group
    s = shell("groups %s" % (user))
    match = re.search(r'\bnpm\b', s['stdout'])
    if match:
        return True
    return False

def add_user(user):
    # Adds user to the npm group
    s = shell("gksu 'gpasswd -a %s npm'" % (user))
    if s["code"] != 0:
        logger.error("NPM group add for %s failed; log output follows:\n%s"%(user,s["stderr"]))
        raise Exception("NPM group add failed, check logs for info")

''' 
    Private commands 
'''

def _get_npm_command(command, as_global, path=None):
    # returns npm command
    if as_global:
        return _get_global_npm_command(command)
    else:
        return _get_local_npm_command(command, path)

def _get_global_npm_command(command):
    # returns global npm command
    os.chdir(NPM_PATH)
    return "gksu -u npm 'npm " + command + " -g'"
    
def _get_local_npm_command(command, install_path):
    # returns local npm command
    if install_path:
        os.chdir(install_path)
    return "npm " + command + " "
