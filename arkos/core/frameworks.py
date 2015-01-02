import uuid

from config import Config
from storage import Storage
from security import Security
from applications import Apps
from sites import Sites, SiteEngines
from certificates import Certificates
from system import System, Filesystems
from databases import Databases, DBEngines
from tracked_services import TrackedServices


FRAMEWORKS = {"system": System, "apps": Apps, "sites": Sites, 
    "databases": Databases, "certificates": Certificates, 
    "filesystems": Filesystems, "security": Security, 
    "tracked_services": TrackedServices, "site_engines": SiteEngines, 
    "database_engines": DBEngines}


class Framework(object):
    REQUIRES = []

    def __init__(self, app, **kwargs):
        self.app = app

    def _assign(self):
        for x in self.app.manager.components:
            setattr(self, x, self.app.manager.components[x])
    
    def _on_init(self):
        self.on_init()
    
    def _on_start(self):
        self.on_start()
    
    def task(self, operation, *args):
        if self.storage:
            self.storage.append("tasks", {"id": uuid.uuid4(), "unit": self.__name__, 
                "order": operation, "data": args})
        else:
            raise Exception("Requires connection to Kraken storage for scheduling")

    def on_init(self):
        pass

    def on_start(self):
        pass


class FrameworkManager(object):
    def __init__(self, app, components=[]):
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
            self.components[x](self.app)
            self.components[x]._on_init()
            self.components[x]._assign()
        for x in self.components:
            self.app.logger.debug("*** Starting %s" % x)
            self.components[x]._on_start()

    def register(self, com):
        self.components.append(com)

    def deregister(self, com):
        self.components.remove(com)
