import os

from arkos.utilities import shell


def install(self, *mods, **kwargs):
    cwd = os.getcwd()
    if "install_path" in kwargs:
        os.chdir(kwargs["install_path"])
    s = shell('npm install %s%s' % (' '.join(x for x in mods), (' --'+' --'.join(x for x in kwargs['opts']) if kwargs.has_key('opts') else '')))
    os.chdir(cwd)
    if s["code"] != 0:
        self.app.log.error('Failed to install %s via npm; log output follows:\n%s'%(' '.join(x for x in mods),s["stderr"]))
        raise Exception('Failed to install %s via npm, check logs for info'%' '.join(x for x in mods))

def remove(self, *mods):
    s = shell('npm uninstall %s' % ' '.join(x for x in mods), stderr=True)
    if s["code"] != 0:
        self.app.log.error('Failed to remove %s via npm; log output follows:\n%s'%(' '.join(x for x in mods),s["stderr"]))
        raise Exception('Failed to remove %s via npm, check logs for info'%' '.join(x for x in mods))

def install_from_package(self, path, stat='production', opts={}):
    cwd = os.getcwd()
    s = shell('npm install %s%s' % (path, '--'+stat if stat else '', ' --'+' --'.join(x+'='+opts[x] for x in opts) if opts else ''), env={'HOME': '/root'})
    os.chdir(cwd)
    if s["code"] != 0:
        self.app.log.error('Failed to install %s via npm; log output follows:\n%s'%(path,s["stderr"]))
        raise Exception('Failed to install %s via npm, check logs for info'%path)
