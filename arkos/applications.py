import imp
import inspect
import json
import os
import pacman
import shutil
import tarfile

from distutils.spawn import find_executable

from arkos import config, storage, signals, logger, tracked_services
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

    def get_module(self, mod_type):
        return getattr(self, "_%s" % mod_type) if hasattr(self, "_%s" % mod_type) else None

    def load(self, verify=True):
        try:
            signals.emit("apps", "pre_load", self)
            if verify:
                self.verify_dependencies()

            # Load the application module into Python
            imp.load_module(self.id, *imp.find_module(self.id,
                [os.path.join(config.get("apps", "app_dir"))]))
            # Get module and its important classes and track them on this object
            for module in self.modules:
                submod = imp.load_module("%s.%s" % (self.id, module),
                    *imp.find_module(module, [os.path.join(config.get("apps", "app_dir"), self.id)]))
                classes = inspect.getmembers(submod, inspect.isclass)
                mgr = None
                for y in classes:
                    if y[0] in ["DatabaseManager", "Site", "BackupController"]:
                        mgr = y[1]
                        break
                logger.debug(" *** Registering %s module on %s" % (module, self.id))
                if module == "database":
                    for y in classes:
                        if issubclass(y[1], mgr) and y[1] != mgr:
                            setattr(self, "_database_mgr", y[1])
                elif module == "website":
                    for y in classes:
                        if issubclass(y[1], mgr) and y[1] != mgr:
                            setattr(self, "_website", y[1])
                elif module == "backup":
                    for y in classes:
                        if issubclass(y[1], mgr) and y[1] != mgr:
                            setattr(self, "_backup", y[1])
                elif module == "api":
                    if hasattr(self, "_backend"):
                        setattr(submod, self.id, self._backend)
                    setattr(self, "_api", submod)
                elif module == "ssl":
                    self.ssl = submod
                else:
                    setattr(self, "_%s" % module, submod)
            # Set up tracking of ports associated with this app
            for s in self.services:
                if s["ports"]:
                    tracked_services.register(self.id, s["binary"], s["name"],
                        self.icon, s["ports"], default_policy=s.get("default_policy", 2),
                        fw=False)
            signals.emit("apps", "post_load", self)
        except Exception, e:
            self.loadable = False
            self.error = "Module error: %s" % str(e)
            logger.warn("Failed to load %s -- %s" % (self.name, str(e)))

    def verify_dependencies(self):
        verify, error, to_pacman = True, "", []
        # If dependency isn't installed, add it to "to install" list
        # If it can't be installed, mark the app as not loadable and say why
        for dep in self.dependencies:
            if dep["type"] == "system":
                if (dep["binary"] and not find_executable(dep["binary"])) \
                or not pacman.is_installed(dep["package"]):
                    to_pacman.append(dep["package"])
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
                        python.install(to_pip)
                    except:
                        error = "Couldn't install %s" % to_pip
                        verify = False
                    finally:
                        if dep.has_key("internal") and dep["internal"]:
                            error = "Restart required"
                            verify = False
        # Execute the "to install" list actions
        if to_pacman:
            pacman.refresh()
        for x in to_pacman:
            try:
                logger.debug(" *** Installing %s..." % x)
                pacman.install(x)
            except:
                error = "Couldn't install %s" % x
                verify = False
        self.loadable = verify
        self.error = error
        return verify

    def install(self, install_deps=True, load=True, force=False, message=DefaultMessage()):
        if self.installed and not force:
            return
        signals.emit("apps", "pre_install", self)
        # Get all apps that this app depends on and install them first
        deps = get_dependent(self.id, "install")
        if install_deps and deps:
            for x in deps:
                logger.debug("Installing %s (dependency for %s)" % (x, self.name))
                message.update("info", "Installing dependencies for %s... (%s)" % (self.name, x))
                _install(x, load=load)
        # Install this app
        logger.debug("Installing %s" % self.name)
        message.update("info", "Installing %s..." % self.name)
        _install(self.id, load=load)
        verify_app_dependencies()
        signals.emit("apps", "post_install", self)

    def uninstall(self, force=False, message=DefaultMessage()):
        signals.emit("apps", "pre_remove", self)
        message.update("info", "Uninstalling application...")
        exclude = ["openssl", "openssh", "nginx", "python2", "git", "nodejs", "npm"]

        # Make sure this app can be successfully removed, and if so also remove
        # any system-level packages that *only* this app requires
        for x in get(installed=True):
            for item in x.dependencies:
                if item["type"] == "app" and item["package"] == self.id and not force:
                    raise Exception("Cannot remove, %s depends on this application" % x.name)
                elif item["type"] == "system":
                    exclude.append(item["package"])

        # Stop any running services associated with this app
        for item in self.dependencies:
            if item["type"] == "system" and not item["package"] in exclude:
                if item.has_key("daemon") and item["daemon"]:
                    services.stop(item["daemon"])
                    services.disable(item["daemon"])
                pacman.remove([item["package"]], purge=config.get("apps", "purge", False))
        logger.debug("Uninstalling %s" % self.name)

        # Remove the app's directory and cleanup the app object
        shutil.rmtree(os.path.join(config.get("apps", "app_dir"), self.id))
        self.loadable = False
        self.installed = False

        # Regenerate the firewall and re-block the abandoned ports
        regen_fw = False
        for x in self.services:
            if x["ports"]:
                regen_fw = True
        if regen_fw:
            tracked_services.deregister(self.id)
        signals.emit("apps", "post_remove", self)

    def ssl_enable(self, cert, sid=""):
        signals.emit("apps", "pre_ssl_enable", self)
        if sid:
            d = self.ssl.ssl_enable(cert, sid)
        else:
            self.ssl.ssl_enable(cert)
        signals.emit("apps", "post_ssl_enable", self)
        return d

    def ssl_disable(self, sid=""):
        signals.emit("apps", "pre_ssl_disable", self)
        if sid:
            self.ssl.ssl_disable(sid)
        else:
            self.ssl.ssl_disable()
        signals.emit("apps", "post_ssl_disable", self)

    def get_ssl_able(self):
        return self.ssl.get_ssl_able()

    def as_dict(self):
        data = {}
        for x in self.__dict__:
            if not x.startswith("_") and x != "ssl":
                data[x] = self.__dict__[x]
        data["is_ready"] = True
        return data


def get(id=None, type=None, loadable=None, installed=None, verify=True):
    data = storage.apps.get("applications")
    if not data:
        data = scan(verify)
    if id or type or loadable or installed:
        type_list = []
        for x in data:
            if x.id == id and (x.loadable or not loadable):
                return x
            elif str(x.installed).lower() == str(installed).lower() and (x.type or not type):
                type_list.append(x)
            elif x.type == type and (x.loadable or not loadable):
                type_list.append(x)
        if type_list:
            return type_list
        return []
    return data

def scan(verify=True):
    signals.emit("apps", "pre_scan")
    app_dir = config.get("apps", "app_dir")
    apps = []
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)

    # Get paths for installed apps, metadata for available ones
    installed_apps = [x for x in os.listdir(app_dir) if not x.startswith(".")]
    available_apps = api("https://%s/api/v1/apps" % config.get("general", "repo_server"),
        crit=False)
    if available_apps:
        available_apps = available_apps["applications"]
    else:
        available_apps = []

    # Create objects for installed apps with appropriate metadata
    for x in installed_apps:
        try:
            with open(os.path.join(app_dir, x, "manifest.json"), "r") as f:
                data = json.loads(f.read())
        except ValueError:
            logger.warn("Failed to load %s due to a JSON parsing error" % x)
            continue
        except IOError:
            logger.warn("Failed to load %s: manifest file inaccessible or not present" % x)
            continue
        logger.debug(" *** Loading %s" % data["id"])
        app = App(**data)
        app.installed = True
        for y in enumerate(available_apps):
            if app.id == y[1]["id"] and app.version != y[1]["version"]:
                app.upgradable = y[1]["version"]
            if app.id == y[1]["id"]:
                app.assets = y[1]["assets"]
                available_apps[y[0]]["installed"] = True
        app.load()
        apps.append(app)

    # Convert available apps payload to objects
    for x in available_apps:
        if not x.get("installed"):
            app = App(**x)
            app.installed = False
            apps.append(app)

    storage.apps.set("applications", apps)

    if verify:
        verify_app_dependencies()
    signals.emit("apps", "post_scan")
    return storage.apps.get("applications")

def verify_app_dependencies():
    apps = [x for x in storage.apps.get("applications") if x.installed]
    for x in apps:
        for dep in x.dependencies:
            # For each app-type dependency in all installed apps...
            if dep["type"] == "app":
                # If the needed app isn't yet installed, put a fail message
                if not dep["package"] in [y.id for y in apps]:
                    x.loadable = False
                    x.error = "Depends on %s, which is not installed" % dep["name"]
                    logger.debug("*** Verify failed for %s -- dependent on %s which is not installed" % (x.name,dep["name"]))
                    # Cascade this fail message to all apps in the dependency chain
                    for z in get_dependent(x.id, "remove"):
                        z = storage.apps.get("applications", z)
                        z.loadable = False
                        z.error = "Depends on %s, which cannot be loaded because %s is not installed" % (x.name,dep["name"])
                # Also put a fail message if the app we depended on failed to load
                elif not storage.apps.get("applications", dep["package"]).loadable:
                    x.loadable = False
                    x.error = "Depends on %s, which also failed" % dep["name"]
                    logger.debug("*** Verify failed for %s -- dependent on %s which failed to load" % (x.name,dep["name"]))
                    # Cascade this fail message to all apps in the dependency chain
                    for z in get_dependent(x.id, "remove"):
                        z = storage.apps.get("applications", z)
                        z.loadable = False
                        z.error = "Depends on %s, which cannot be loaded because %s failed to load" % (x.name,dep["name"])

def get_dependent(id, op):
    metoo = []
    apps = storage.apps.get("applications")
    installed = [x.id for x in apps if x.installed]
    # If any apps depend on me, flag them to be removed also
    if op == "remove":
        for app in apps:
            for dep in app.dependencies:
                if dep["type"] == "app" and dep["package"] == id:
                    metoo.append(app)
                    metoo += get_dependent(app.id, "remove")
    # If I need any other apps to install, flag them to be installed also
    elif op == "install":
        app = next(x for x in apps if x.id == id)
        for dep in app.dependencies:
            if dep["type"] == "app" and dep["package"] not in installed:
                metoo.append(dep["package"])
                metoo += get_dependent(dep["package"], "install")
    return metoo

def _install(id, load=True):
    app_dir = config.get("apps", "app_dir")
    # Download and extract the app source package
    data = api("https://%s/api/v1/apps/%s" % (config.get("general", "repo_server"), id),
        returns="raw", crit=True)
    with open(os.path.join(app_dir, "%s.tar.gz" % id), "wb") as f:
        f.write(data)
    with tarfile.open(os.path.join(app_dir, "%s.tar.gz" % id), "r:gz") as t:
        t.extractall(app_dir)
    os.unlink(os.path.join(app_dir, "%s.tar.gz" % id))
    # Read the app's metadata and create an object
    with open(os.path.join(app_dir, id, "manifest.json")) as f:
        data = json.loads(f.read())
    app = get(id)
    for x in data:
        setattr(app, x, data[x])
    app.upgradable = ""
    app.installed = True
    if load:
        app.load()
