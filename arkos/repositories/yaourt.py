from arkos import logger
from arkos.utilities import shell

def install(*mods):
    # Installs a set of yaourt packages.
    s = shell("yaourt -S %s" % " ".join(x for x in mods))
    if s["code"] != 0:
        logger.error("Failed to install %s via yaourt; %s"%(" ".join(x for x in mods),s["stderr"]))
        raise Exception("Failed to install %s via yaourt, check logs for info"%" ".join(x for x in mods))
    
def remove(*mods):
    # Remove a set of installed yaourt package.
    s = shell("yaourt -R %s" % " ".join(x for x in mods))
    if s["code"] != 0:
        logger.error("Failed to remove %s via yaourt; %s"%(" ".join(x for x in mods),s["stderr"]))
        raise Exception("Failed to remove %s via yaourt, check logs for info"%" ".join(x for x in mods))

def is_installed(name):
    # Verifies if package is installed
    s = shell("yaourt - Qi %s" % (name))
    if s['code'] != 0:
        return False
    return True