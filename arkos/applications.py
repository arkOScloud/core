import base64
import imp
import inspect
import json
import os
import pacman
import shutil
import tarfile

from distutils.spawn import find_executable

from arkos import config, storage, logger, tracked_services
from arkos.system import services
from arkos.languages import python
from arkos.utilities import api, DefaultMessage


class App:
    def __init__(self, **entries):
        self.__dict__.update(entries)
        self.loadable = False
        self.upgradable = ""
        self.installed = False
        self.error = ""

    def get_module(self, mtype):
        return getattr(self, "_%s"%mtype) if hasattr(self, "_%s"%mtype) else None
    
    def load(self, verify=True):
        try:
            module = imp.load_module(self.id, *imp.find_module(self.id, [os.path.join(config.get("apps", "app_dir"))]))
            for x in self.modules:
                submod = imp.load_module("%s.%s"%(self.id,x), *imp.find_module(x, [os.path.join(config.get("apps", "app_dir"), self.id)]))
                classes = inspect.getmembers(submod, inspect.isclass)
                mgr = None
                for y in classes:
                    if y[0] in ["DatabaseManager", "Site", "BackupController"]:
                        mgr = y[1]
                        break
                if x == "database":
                    for y in classes:
                        if issubclass(y[1], mgr) and y[1] != mgr:
                            setattr(self, "_database_mgr", y[1])
                elif x == "website":
                    for y in classes:
                        if issubclass(y[1], mgr) and y[1] != mgr:
                            setattr(self, "_website", y[1])
                elif x == "backup":
                    for y in classes:
                        if issubclass(y[1], mgr) and y[1] != mgr:
                            setattr(self, "_backup", y[1])
                else:
                    setattr(self, "_%s"%x, submod)
            if verify:
                self.verify_dependencies()
            for s in self.services:
                if s["ports"]:
                    tracked_services.register(self.id, s["binary"], s["name"], 
                        self.icon, s["ports"], fw=False)
        except Exception, e:
            self.loadable = False
            self.error = "Module error: %s" % str(e)
            logger.warn("Failed to load %s -- %s" % (self.name, str(e)))
    
    def verify_dependencies(self):
        verify, error = True, ""
        for dep in self.dependencies:
            if dep["type"] == "system":
                to_pacman = ""
                if (dep["binary"] and not find_executable(dep["binary"])) \
                or not pacman.is_installed(dep["package"]):
                    to_pacman = dep["package"]
                if to_pacman:
                    try:
                        logger.debug(" *** Installing %s..." % to_pacman)
                        pacman.query()
                        pacman.install([to_pacman])
                    except:
                        error = "Couldn't install %s" % to_pacman
                        verify = False
                    finally:
                        if dep.has_key("internal") and dep["internal"]:
                            error = "Restart required"
                            verify = False
            if dep["type"] == "python":
                to_pip = ""
                if dep["module"]:
                    try:
                        __import__(dep["module"])
                    except ImportError:
                        to_pip = dep["package"]
                else:
                    if not python.is_installed(dep["package"]):
                        to_pip = dep["package"]
                if to_pip:
                    try:
                        logger.debug(" *** Installing %s (via pip)..." % to_pip)
                        python.install([to_pip])
                    except:
                        error = "Couldn't install %s" % to_pip
                        verify = False
                    finally:
                        if dep.has_key("internal") and dep["internal"]:
                            error = "Restart required"
                            verify = False
        self.loadable = verify
        self.error = error
        return verify
    
    def install(self, install_deps=True, load=True, message=DefaultMessage()):
        deps = get_dependent(self.id, "install")
        if install_deps and deps:
            for x in deps:
                message.update("info", "Installing dependencies for %s... (%s)" % (self.name, x))
                _install(x, load=load)
        message.update("info", "Installing %s..." % self.name)
        _install(self.id, load=load)
        for x in self.services:
            if x["ports"]:
                regen_fw = True
                tracked_services.register(self.id, x["binary"], x["name"], self.icon, x["ports"])
    
    def uninstall(self, force=False, message=DefaultMessage()):
        message.update("info", "Uninstalling application...")
        exclude = ['openssl', 'openssh', 'nginx', 'python2', 'git']
        for app in storage.apps.get("applications"):
            for item in app.dependencies:
                if item["type"] == "app" and item["package"] == self.id and not force:
                    raise Exception("Cannot remove, %s depends on this application" % item["package"])
                elif item["type"] == "system":
                    exclude.append(item["package"])
        for item in self.dependencies:
            if item["type"] == "system" and not item["package"] in exclude:
                if item.has_key("daemon") and item["daemon"]:
                    services.stop(item["daemon"])
                    services.disable(item["daemon"])
                pacman.remove([item["package"]], purge=config.get("apps", "purge", False))
        shutil.rmtree(os.path.join(config.get("apps", "app_dir"), self.id))
        self.loadable = False
        self.installed = False
        regen_fw = False
        for x in self.services:
            if x["ports"]:
                regen_fw = True
        if regen_fw:
            tracked_services.deregister(self.id)
    
    def as_dict(self):
        data = {}
        for x in self.__dict__:
            if not x.startswith("_"):
                data[x] = self.__dict__[x]
        data["is_ready"] = True
        return data


def get(id=None, type=None, loadable=None, installed=None, verify=True):
    data = storage.apps.get("applications")
    if not data:
        data = scan(verify)
    if id or type or loadable or installed:
        tlist = []
        for x in data:
            if x.id == id and (x.loadable or not loadable):
                return x
            elif str(x.installed).lower() == str(installed).lower() and (x.type or not type):
                tlist.append(x)
            elif x.type == type and (x.loadable or not loadable):
                tlist.append(x)
        if tlist:
            return tlist
        return []
    return data

def scan(verify=True):
    apps = []
    idata = [app for app in os.listdir(config.get("apps", "app_dir")) if not app.startswith(".")]
    adata = api('https://%s/api/v1/apps' % config.get("general", "repo_server"), crit=False)
    if adata:
        adata = adata["applications"]
    else:
        adata = []

    for app in idata:
        try:
            with open(os.path.join(config.get("apps", "app_dir"), app, "manifest.json"), "r") as f:
                data = json.loads(f.read())
        except ValueError:
            logger.warn("Failed to load %s due to a JSON parsing error" % app)
            continue
        logger.debug(" *** Loading %s" % data["id"])
        a = App(**data)
        a.installed = True
        for y in enumerate(adata):
            if a.id == y[1]["id"] and a.version != y[1]["version"]:
                a.upgradable = y[1]["version"]
            if a.id == y[1]["id"]:
                adata[y[0]]["installed"] = True
        a.load()
        apps.append(a)
    
    for x in adata:
        if not x.get("installed"):
            app = App(**x)
            app.installed = False
            apps.append(app)

    storage.apps.set("applications", apps)
    
    if verify:
        verify_app_dependencies()
    return storage.apps.get("applications")

def verify_app_dependencies():
    apps = [x for x in storage.apps.get("applications") if x.installed]
    for x in apps:
        for dep in x.dependencies:
            if dep["type"] == "app":
                if not dep["package"] in [y.id for y in apps]:
                    x.loadable = False
                    x.error = "Depends on %s, which is not installed" % dep["name"]
                    logger.debug("*** Verify failed for %s -- dependent on %s which is not installed" % (x.name,dep["name"]))
                    for z in get_dependent(x.id, "remove"):
                        z = storage.apps.get("installed", z)
                        z.loadable = False
                        z.error = "Depends on %s, which cannot be loaded because %s is not installed" % (x.name,dep["name"])
                elif not storage.apps.get("applications", dep["package"]).loadable:
                    x.loadable = False
                    x.error = "Depends on %s, which also failed" % dep["name"]
                    logger.debug("*** Verify failed for %s -- dependent on %s which failed to load" % (x.name,dep["name"]))
                    for z in get_dependent(x.id, "remove"):
                        z = storage.apps.get("installed", z)
                        z.loadable = False
                        z.error = "Depends on %s, which cannot be loaded because %s failed to load" % (x.name,dep["name"])

def get_dependent(id, op):
    metoo = []
    apps = storage.apps.get("applications")
    if op == 'remove':
        for i in apps:
            for dep in i.dependencies:
                if dep['type'] == 'app' and dep['package'] == id:
                    metoo.append(i)
                    metoo += get_dependent(i.id, 'remove')
    elif op == 'install':
        i = next(x for x in apps if x.id == id)
        for dep in i.dependencies:
            if dep["type"] == 'app' and dep['package'] not in [x.id for x in apps if x.installed]:
                metoo.append(dep['package'])
                metoo += get_dependent(dep['package'], 'install')
    return metoo

def _install(id, load=True):
    data = api('https://%s/api/v1/apps/%s' % (config.get("general", "repo_server"), id),
        returns='raw', crit=True)
    with open(os.path.join(config.get("apps", "app_dir"), 'plugin.tar.gz'), 'wb') as f:
        f.write(data)
    with tarfile.open(os.path.join(config.get("apps", "app_dir"), 'plugin.tar.gz'), 'r:gz') as t:
        t.extractall(config.get("apps", "app_dir"))
    os.unlink(os.path.join(config.get("apps", "app_dir"), 'plugin.tar.gz'))
    with open(os.path.join(config.get("apps", "app_dir"), id, "manifest.json")) as f:
        data = json.loads(f.read())
    app = get(id)
    for x in data:
        setattr(app, x, data[x])
    app.upgradable = ""
    app.installed = True
    if load:
        app.load()
