from arkos.core.utilities import shell


class Packages(object):
    def install(self, packages, query=False, needed=True):
        s = shell("pacman -S%s %s%s" % (("y" if query else ""),("--needed " if needed else "")," ".join(packages)))
        if s["code"] != 0:
            raise Exception("Failed to install %s: %s" % (" ".join(packages), str(s["stderr"])))

    def remove(self, packages, purge=False):
        s = shell("pacman -R%s %s" % (("n" if purge else "")," ".join(packages)))
        if s["code"] != 0:
            raise Exception("Failed to remove %s: %s" % (" ".join(packages), str(s["stderr"])))

    def is_installed(self, package):
        s = shell("pacman -Q %s" % package)
        if s["code"] != 0:
            raise Exception("Failed to query %s: %s" % (package, str(s["stderr"])))
