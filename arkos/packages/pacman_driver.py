import pacman

from . import PackageManager


class PacmanDriver(PackageManager):
    def refresh(self):
        pacman.refresh()

    def upgrade(self):
        pacman.upgrade()

    def get_installed(self):
        return pacman.get_installed()

    def get_available(self):
        return pacman.get_available()

    def get_upgradable(self):
        return list(filter(lambda x: x["upgradable"], pacman.get_installed()))

    def install(self, packages, nthread=None):
        pacman.install(packages)

    def remove(self, packages, purge=False, nthread=None):
        pacman.remove(packages, purge=purge)
