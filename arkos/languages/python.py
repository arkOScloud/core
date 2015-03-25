import os
import stat
import shutil

from arkos import logger
from arkos.utilities import shell


def install(*mods):
    s = shell('pip2 install %s' % ' '.join(x for x in mods))
    if s["code"] != 0:
        logger.error('Failed to install %s via PyPI; %s'%(' '.join(x for x in mods),s["stderr"]))
        raise Exception('Failed to install %s via PyPI, check logs for info'%' '.join(x for x in mods))

def remove(*mods):
    s = shell('pip2 uninstall %s' % ' '.join(x for x in mods))
    if s["code"] != 0:
        logger.error('Failed to remove %s via PyPI; %s'%(' '.join(x for x in mods),s["stderr"]))
        raise Exception('Failed to remove %s via PyPI, check logs for info'%' '.join(x for x in mods))

def is_installed(name):
    s = shell('pip2 freeze')
    for x in s["stdout"].split('\n'):
        if name.lower() in x.split('==')[0].lower():
            return True
    return False
