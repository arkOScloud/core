class PackageManager:
    def __init__(self, cache=[]):
        self.cache = cache

    def refresh(self):
        pass

    def upgrade(self):
        pass

    def get_installed(self):
        pass

    def get_available(self):
        pass

    def get_upgradable(self):
        pass

    def install(self, *packages):
        pass

    def uninstall(self, *packages):
        pass
