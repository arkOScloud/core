import imp

from arkos.core.frameworks import Framework


class SiteEngines(Framework):
    REQUIRES = ["apps", "databases", "system"]

    def on_start(self):
        self.path = self.app.conf.get("apps", "app_dir")
        self.types = {}
        self.full_scan()

    def full_scan(self):
        # Scan for new website apps
        for x in self.apps.get(type="website"):
            self.add(x)

    def add(self, app):
        # Add a new website app introduced during runtime
        if not x.has_key("verify") or not x["verify"] == "pass":
            return
        try:
            mod = imp.load_module(x["pid"], *imp.find_module(x["pid"], [self.path]))
        except Exception, e:
            self.log.warn(' *** Plugin not loadable: ' + x["pid"])
            self.log.warn(" *** "+str(e))
        xmod = getattr(mod, x["website_plugin"])
        self.types[x["website_plugin"]] = xmod(self.system, self.databases)

    def get(self, pid):
        return self.types[pid if type(pid) == str else pid["pid"]]


class SiteEngine(object):
    def __init__(self, system, databases):
        self.system = system
        self.databases = databases

    def pre_install(self, name, vars):
        pass

    def post_install(self, name, path, vars):
        pass

    def pre_remove(self, name, path):
        pass

    def post_remove(self, name):
        pass

    def ssl_enable(self, path, cfile, kfile):
        pass

    def ssl_disable(self, path):
        pass
