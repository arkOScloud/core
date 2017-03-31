import apt

from . import PackageManager
from arkos.utilities.errors import InvalidConfigError


class APTDriver(PackageManager):
    def __init__(self, cache=[]):
        super(PackageManager).__init__(cache)
        if not self.cache:
            self._open_cache()

    def _open_cache(self):
        cache = apt.Cache()
        cache.open(None)
        self.cache = cache

    def refresh(self):
        self._open_cache()
        self.cache.update()
        self.cache.open(None)

    def upgrade(self):
        self.cache.upgrade()
        self.cache.commit()
        self._open_cache()

    def _process_info(self, x):
        info = self.cache[x]
        processed_info = {
            "id": x,
            "version": info.installed.version
            if info.installed else info.versions[0].version,
            "upgradable": info.is_upgradable,
            "installed": info.is_installed
        }
        if info.installed and info.installed.version:
            processed_info.update({
                "source": info.versions[0].source_name,
                "size": info.versions[0].size,
                "installed_size": info.versions[0].installed_size,
                "sha256": info.versions[0].sha256,
                "architecture": info.versions[0].architecture,
                "description": info.versions[0].description,
                "homepage": info.versions[0].homepage
            })
        return processed_info

    def get_installed(self):
        install = filter(
            lambda x: self.cache[x].is_installed, self.cache.keys())
        return list(map(lambda x: self._process_info(x), install))

    def get_available(self):
        remove = filter(
            lambda x: not self.cache[x].is_installed, self.cache.keys())
        return list(map(lambda x: self._process_info(x), remove))

    def get_upgradable(self):
        upgrade = filter(
            lambda x: self.cache[x].is_upgradable, self.cache.keys())
        return list(map(lambda x: self._process_info(x), upgrade))

    def install(self, packages, nthread=None):
        for x in packages:
            pkg = self.cache.get(x)
            if not pkg:
                raise InvalidConfigError(
                    "Package {0} not found in cache".format(x),
                    nthread=nthread
                )
            pkg.mark_install()
            self.cache.commit()
        self._open_cache()

    def remove(self, packages, purge=False, nthread=None):
        for x in packages:
            pkg = self.cache.get(x)
            if not pkg:
                raise InvalidConfigError(
                    "Package {0} not found in cache".format(x),
                    nthread=nthread
                )
            pkg.mark_delete(purge=purge)
            self.cache.commit()
        self._open_cache()
