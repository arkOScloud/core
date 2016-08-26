from arkos import logger
from arkos.utilities import shell


def install(*mods):
    """ Installs a set of yaourt packages. """
    s = shell("yaourt -S {0}".format(" ".join(x for x in mods)))
    if s["code"] != 0:
        logger.error("Failed to install {0} via yaourt; {1}"
                     .format(" ".join(x for x in mods), s["stderr"]))
        raise Exception("Failed to install {0} via yaourt, check logs for info"
                        .format(" ".join(x for x in mods)))


def remove(*mods):
    """ Remove a set of installed yaourt package. """
    s = shell("yaourt -R {0}".format(" ".join(x for x in mods)))
    if s["code"] != 0:
        logger.error("Failed to remove {0} via yaourt; {1}"
                     .format(" ".join(x for x in mods), s["stderr"]))
        raise Exception("Failed to remove {0} via yaourt, check logs for info"
                        .format(" ".join(x for x in mods)))


def is_installed(name):
    """ Verifies if package is installed """
    s = shell("yaourt - Qi {0}".format(name))
    if s['code'] != 0:
        return False
    return True
