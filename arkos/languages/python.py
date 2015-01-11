import os
import stat
import shutil

from arkos.utilities import shell


def install(self, *mods):
    s = shell('pip install %s' % ' '.join(x for x in mods))
    if s["code"] != 0:
        self.app.log.error('Failed to install %s via PyPI; %s'%(' '.join(x for x in mods),s["stderr"]))
        raise Exception('Failed to install %s via PyPI, check logs for info'%' '.join(x for x in mods))

def remove(self, *mods):
    s = shell('pip uninstall %s' % ' '.join(x for x in mods))
    if s["code"] != 0:
        self.app.log.error('Failed to remove %s via PyPI; %s'%(' '.join(x for x in mods),s["stderr"]))
        raise Exception('Failed to remove %s via PyPI, check logs for info'%' '.join(x for x in mods))

def is_installed(self, name):
    s = shell('pip freeze')
    for x in s["stdout"].split('\n'):
        if name.lower() in x.split('==')[0].lower():
            return True
    return False
