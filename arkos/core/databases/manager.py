import imp

from arkos.core import Framework


class DBEngines(Framework):
    REQUIRES = ["apps", "services"]

    def on_start(self):
        self.types = {}
        self.full_scan()

    def full_scan(self):
        # Scan for new database apps
        for x in self.apps.get(type="database"):
            self.add(x)

    def add(self, app):
        # Add a new database app introduced during runtime
        if not x.has_key("verify") or not x["verify"] == "pass":
            continue
        try:
            mod = imp.load_module(x["pid"], *imp.find_module(x["pid"], [self.path]))
        except Exception, e:
            self.log.warn(' *** Plugin not loadable: ' + x["pid"])
            self.log.warn(str(e))
        xmod = getattr(mod, x["database_plugin"])
        self.types[x["database_plugin"]] = xmod(self.services)

    def get(self, pid):
        return self.types[pid if type(pid) == str else pid["pid"]]


class DBBasicEngine(object):
    def __init__(self, services):
        self.services = services

    def add(self):
        pass

    def remove(self):
        pass

    def get_dbs(self):
        pass

    def execute(self):
        pass


class DBUserEngine(object):
    def chperm(self):
        pass

    def get_users(self):
        pass

    def usermod(self):
        pass
