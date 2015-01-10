import base64
import imp
import json
import os
import shutil
import tarfile

from distutils.spawn import find_executable

from arkos import config, storage, logger
from arkos.system import packages, services
from arkos.languages import python
from arkos.utilities import api, dictfilter, DefaultMessage


class App:
    def __init__(self, **entries):
        self.__dict__.update(entries)
        self.loadable = False
        self.error = ""

    def get_module(self, mtype):
        if mtype == "kraken":
            return self._kraken if hasattr(self, "_kraken") else None
        elif mtype == "genesis":
            return self._genesis if hasattr(self, "_genesis") else None
        elif mtype == "cli":
            return self._cli if hasattr(self, "_cli") else None
        return None
    
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
                if item["daemon"]:
                    services.stop(item["daemon"])
                    services.disable(item["daemon"])
                packages.remove([item["package"]], purge=config.get("apps", "purge", False))
        shutil.rmtree(os.path.join(config.get("apps", "app_dir"), id))
        storage.app.remove("installed", self)


def get():
    apps = []
    applist = [app for app in os.listdir(config.get("apps", "app_dir")) if not app.startswith(".")]
    applist = list(set(applist))

    while len(applist) > 0:
        app = applist[-1]
        try:
            with open(os.path.join(config.get("apps", "app_dir"), app, "manifest.json"), "r") as f:
                data = json.loads(f.read())
        except Exception, e:
            continue
        apps.append(App(**data))
        applist.remove(app)
    return apps

def get_available():
    return api('https://%s/' % config.get("general", "repo_server"), 
        post={'get': 'list'}, returns='raw', crit=True)

def get_updatable():
    upgradeable = []
    if not storage.apps.get("available"):
        storage.apps.set("available", get_available())
    if not storage.apps.get("installed"):
        storage.apps.set("installed", get_installed())
    for x in storage.apps.get("available"):
        for y in storage.apps.get("installed"):
            if x.id == y.id and x.version != y.version:
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
                    self.app.logger.debug("*** Verify failed for %s -- dependent on %s which is not installed" % (x.name,dep["name"]))
                    for z in get_dependent(x.id, "remove"):
                        z = storage.apps.get("installed", z)
                        z.loadable = False
                        z.error = "Depends on %s, which cannot be loaded because %s is not installed" % (x.name,dep["name"])
                elif not storage.apps.get("installed", dep["package"]).loadable:
                    x.loadable = False
                    x.error = "Depends on %s, which also failed" % dep["name"]
                    self.app.logger.debug("*** Verify failed for %s -- dependent on %s which failed to load" % (x.name,dep["name"]))
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
                    metoo += self.verify_operation(i.id, 'remove')
    elif op == 'install':
        i = next(x for x in avail if x["id"] == id)
        for dep in i["dependencies"]:
            if dep["type"] == 'app' and dep['package'] not in [x["pid"] for x in inst]:
                metoo.append(dep['package'])
                metoo += self.verify_operation(dep['package'], 'install')
    return metoo

def install(id, install_deps=True, message=DefaultMessage()):
    deps = get_dependent(id, "install")
    if install_deps and deps:
        if message:
            message.update("info", "Installing dependencies for %s..." % id)
        for x in deps:
            try:
                _install(x)
            except Exception, e:
                if message:
                    message.complete("error", str(e))
                    return
                else:
                    raise
    if message:
        message.update("info", "Installing %s..." % id)
    try:
        _install(id)
    except Exception, e:
        if message:
            message.complete("error", str(e))
            return
        else:
            raise

def _install(id):
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
        storage.app.append("installed", App(**data))
