import base64
import imp
import inspect
import json
import os
import shutil
import tarfile

from distutils.spawn import find_executable

from arkos import config, storage, logger, tracked_services
from arkos.system import packages, services
from arkos.languages import python
from arkos.utilities import api, DefaultMessage


class App:
    def __init__(self, **entries):
        self.__dict__.update(entries)
        self.loadable = False
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
                if dep["binary"] and not find_executable(dep["binary"]):
                    to_pacman = dep["package"]
                elif packages.is_installed(dep["package"]):
                    to_pacman = dep["package"]
                if to_pacman:
                    try:
                        logger.debug(" *** Installing %s..." % to_pacman)
                        packages.install([to_pacman], query=True)
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
    
    def uninstall(self, force=False, message=DefaultMessage()):
        if message:
            message.update("info", "Uninstalling application...")
        exclude = ['openssl', 'openssh', 'nginx', 'python2', 'git']
        for app in storage.apps.get("installed"):
            for item in app.dependencies:
                if item["type"] == "app" and item["package"] == id and not force:
                    if message:
                        message.complete("error", "Cannot remove, %s depends on this application" % item["package"])
                        return
                    else:
                        raise Exception("Cannot remove, %s depends on this application" % item["package"])
                elif item["type"] == "system":
                    exclude.append(item["package"])
        for item in self.dependencies:
            if item["type"] == "system" and not item["package"] in exclude:
                if item.has_key("daemon") and item["daemon"]:
                    services.stop(item["daemon"])
                    services.disable(item["daemon"])
                packages.remove([item["package"]], purge=config.get("apps", "purge", False))
        shutil.rmtree(os.path.join(config.get("apps", "app_dir"), id))
        storage.apps.remove("installed", self)
        regen_fw = False
        for x in self.services:
            if x["ports"]:
                regen_fw = True
        if regen_fw:
            tracked_services.deregister(self.id)


def get(id=None, type=None, verify=True):
    data = storage.apps.get("installed")
    if not data:
        data = scan(verify)
    if id or type:
        tlist = []
        for x in data:
            if x.id == id:
                return x
            elif x.type == type:
                tlist.append(x)
        if tlist:
            return tlist
        return None
    return data

def scan(verify=True):
    apps = []
    applist = [app for app in os.listdir(config.get("apps", "app_dir")) if not app.startswith(".")]

    for app in applist:
        try:
            with open(os.path.join(config.get("apps", "app_dir"), app, "manifest.json"), "r") as f:
                data = json.loads(f.read())
        except ValueError:
            logger.warn("Failed to load %s due to a JSON parsing error" % app)
            continue
        logger.debug(" *** Loading %s" % data["id"])
        a = App(**data)
        a.load()
        apps.append(a)
    storage.apps.set("installed", apps)
    #if verify:
        #verify_app_dependencies()
    return storage.apps.get("installed")

def get_available(id=None):
    data = storage.apps.get("available")
    if not data:
        data = scan_available()
    if id:
        for x in data:
            if x["id"] == id:
                return x
        return None
    return data

def scan_available():
    data = api('https://%s/apps' % config.get("general", "repo_server"), 
        returns='raw', crit=True)
    storage.apps.set("available", data)
    return data

def get_updatable(id=None):
    data = storage.apps.get("updatable")
    if not data:
        data = scan_updatable()
    if id:
        for x in data:
            if x.id == id:
                return x
        return None
    return data

def scan_updatable():
    upgradeable = []
    if not storage.apps.get("available"):
        storage.apps.set("available", get_available())
    if not storage.apps.get("installed"):
        storage.apps.set("installed", get())
    for x in storage.apps.get("available"):
        for y in storage.apps.get("installed"):
            if x["id"] == y.id and x["version"] != y.version:
                upgradeable.append(x)
                break
    return upgradeable

def verify_app_dependencies():
    apps = storage.apps.get("installed")
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
                elif not storage.apps.get("installed", dep["package"]).loadable:
                    x.loadable = False
                    x.error = "Depends on %s, which also failed" % dep["name"]
                    logger.debug("*** Verify failed for %s -- dependent on %s which failed to load" % (x.name,dep["name"]))
                    for z in get_dependent(x.id, "remove"):
                        z = storage.apps.get("installed", z)
                        z.loadable = False
                        z.error = "Depends on %s, which cannot be loaded because %s failed to load" % (x.name,dep["name"])

def get_dependent(id, op):
    metoo = []
    inst = storage.apps.get("installed") or get()
    avail = storage.apps.get("available") or get_available()
    if op == 'remove':
        for i in inst:
            for dep in i.dependencies:
                if dep['type'] == 'app' and dep['package'] == id:
                    metoo.append(i)
                    metoo += get_dependent(i.id, 'remove')
    elif op == 'install':
        i = next(x for x in avail if x["id"] == id)
        for dep in i["dependencies"]:
            if dep["type"] == 'app' and dep['package'] not in [x["pid"] for x in inst]:
                metoo.append(dep['package'])
                metoo += get_dependent(dep['package'], 'install')
    return metoo

def install(id, install_deps=True, load=True, message=DefaultMessage()):
    deps = get_dependent(id, "install")
    if install_deps and deps:
        if message:
            message.update("info", "Installing dependencies for %s..." % id)
        for x in deps:
            try:
                _install(x, load=load)
            except Exception, e:
                if message:
                    message.complete("error", str(e))
                    return
                else:
                    raise
    if message:
        message.update("info", "Installing %s..." % id)
    try:
        _install(id, load=load)
    except Exception, e:
        if message:
            message.complete("error", str(e))
            return
        else:
            raise
    a = get(id)
    for x in a.services:
        if x["ports"]:
            regen_fw = True
            tracked_services.register(a.id, x["binary"], x["name"], a.icon, x["ports"])

def _install(id, load=True):
    data = api('https://%s/apps/%s' % (config.get("general", "repo_server"), id), crit=True)
    if data['status'] == 200:
        with open(os.path.join(config.get("apps", "app_dir"), 'plugin.tar.gz'), 'wb') as f:
            f.write(base64.b64decode(data['info']))
    else:
        raise Exception('Application retrieval failed - %s' % str(data['info']))
    with tarfile.open(os.path.join(config.get("apps", "app_dir"), 'plugin.tar.gz'), 'r:gz') as t:
        t.extractall(config.get("apps", "app_dir"))
    os.unlink(os.path.join(config.get("apps", "app_dir"), 'plugin.tar.gz'))
    with open(os.path.join(config.get("apps", "app_dir"), id, "manifest.json")) as f:
        data = json.loads(f.read())
    app = App(**data)
    if load:
        app.load()
    storage.apps.add("installed", app)
