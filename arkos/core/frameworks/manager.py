from arkos.core.config import Config
from arkos.core.updates import Updates
from arkos.core.storage import Storage
from arkos.core.security import Security
from arkos.core.applications import Apps
from arkos.core.sites import Sites, SiteEngines
from arkos.core.certificates import Certificates
from arkos.core.system import System, Filesystems
from arkos.core.databases import Databases, DBEngines
from arkos.core.tracked_services import TrackedServices


FRAMEWORKS = {"system": System, "apps": Apps, "sites": Sites, 
    "databases": Databases, "certificates": Certificates, 
    "filesystems": Filesystems, "security": Security, 
    "tracked_services": TrackedServices, "site_engines": SiteEngines, 
    "database_engines": DBEngines, "updates": Updates}


class FrameworkManager(object):
    def __init__(self, app, components={}):
        self.components = components
        self.app = app

    def start(self):
        # Create map of required dependency frameworks
        if not self.components:
            for x in FRAMEWORKS:
                self.register({x: FRAMEWORKS[x]})
        else:
            comp, self.components = self.components, []
            for x in comp:
                self.register({x: FRAMEWORKS[x]})
            for x in self.components:
                for y in self.components[x].REQUIRED:
                    if y in self.components:
                        continue
                    self.register({y: FRAMEWORKS[y]})
        for x in self.components:
            self.app.logger.debug("*** Initializing %s" % x)
            self.components[x] = self.components[x](self.app)
            self.components[x]._on_init()
        for x in self.components:
            self.components[x]._assign()
        for x in self.components:
            self.app.logger.debug("*** Starting %s" % x)
            self.components[x]._on_start()

    def register(self, com):
        n = com.keys()[0]
        self.components[n] = com[n]

    def deregister(self, com):
        del self.components[com]
