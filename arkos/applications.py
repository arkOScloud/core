"""
Classes and functions for management of arkOS applications.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import imp
import inspect
import json
import os
import pacman
import shutil
import tarfile
import traceback

from distutils.spawn import find_executable

from arkos import config, storage, signals, logger, tracked_services
from arkos.system import services
from arkos.languages import python
from arkos.utilities import api, DefaultMessage


class App:
    """Class representing an arkOS Application."""

    def __init__(self, **entries):
        """
        Initialize application properties.

        :param entries: ``**kwargs`` of application metadata to populate.
        """
        self.__dict__.update(entries)
        self.loadable = False
        self.upgradable = ""
        self.installed = False
        self.error = ""

    def get_module(self, mod_type):
        """
        Helper function to get linked auxillary modules.

        :param mod_type: Type of module to return (``backup``, ``ssl``, etc)
        :returns: Auxillary module (Backup, SSL, etc)
        :rtype: module
        """
        return getattr(self, "_{0}".format(mod_type), None)

    def load(self, verify=True):
        """
        Load an application and associated metadata into the running process.

        :param bool verify: Verify System/Python/OS dependencies
        """
        try:
            signals.emit("apps", "pre_load", self)
            if verify:
                self.verify_dependencies()

            # Load the application module into Python
            app_dir = config.get("apps", "app_dir")
            imp.load_module(self.id, *imp.find_module(self.id, [app_dir]))
            # Get module and its important classes and track them here
            for module in self.modules:
                submod = imp.load_module(
                    "{0}.{1}".format(self.id, module),
                    *imp.find_module(module, [os.path.join(app_dir, self.id)])
                )
                classes = inspect.getmembers(submod, inspect.isclass)
                mgr = None
                for y in classes:
                    if y[0] in ["DatabaseManager", "Site", "BackupController"]:
                        mgr = y[1]
                        break
                debug_str = " *** Registering {0} module on {1}"
                logger.debug(debug_str.format(module, self.id))
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
                    setattr(submod, self.id, getattr(self, "_backend", None))
                    setattr(self, "_api", submod)
                elif module == "ssl":
                    self.ssl = submod
                else:
                    setattr(self, "_{0}".format(module), submod)
            # Set up tracking of ports associated with this app
            for s in self.services:
                if s["ports"]:
                    tracked_services.register(
                        self.id, s["binary"], s["name"], self.icon, s["ports"],
                        default_policy=s.get("default_policy", 2), fw=False
                    )
            signals.emit("apps", "post_load", self)
        except Exception as e:
            self.loadable = False
            self.error = "Module error: {0}".format(e)
            logger.warn("Failed to load {0} -- {1}".format(self.name, str(e)))
            logger.warn("Stacktrace follows:")
            logger.warn(traceback.format_exc())

    def verify_dependencies(self):
        """
        Verify that the associated dependencies are all properly installed.

        Checks system-level packages, Python packages and arkOS Apps for
        installed status. Sets ``self.loadable`` with verify status and
        ``self.error`` with error message encountered on check.

        :returns: True if all verify checks passed
        :rtype: bool
        """
        verify, error, to_pacman = True, "", []
        # If dependency isn't installed, add it to "to install" list
        # If it can't be installed, mark the app as not loadable and say why
        for dep in self.dependencies:
            if dep["type"] == "system":
                if (dep["binary"] and not find_executable(dep["binary"])) \
                        or not pacman.is_installed(dep["package"]):
                    to_pacman.append(dep["package"])
                    if dep.get("internal"):
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
                        debug_str = " *** Installing {0} (via pip)..."
                        logger.debug(debug_str.format(to_pip))
                        python.install(to_pip)
                    except:
                        error = "Couldn't install {0}".format(to_pip)
                        verify = False
                    finally:
                        if dep.get("internal"):
                            error = "Restart required"
                            verify = False
        # Execute the "to install" list actions
        if to_pacman:
            pacman.refresh()
        for x in to_pacman:
            try:
                logger.debug(" *** Installing {0}...".format(x))
                pacman.install(x)
            except:
                error = "Couldn't install {0}".format(x)
                verify = False
        self.loadable = verify
        self.error = error
        return verify

    def install(self, install_deps=True, load=True, force=False,
                message=DefaultMessage()):
        """
        Install the arkOS application to the system.

        :param bool install_deps: Install the app's dependencies too?
        :param bool load: Load the app after install?
        :param bool force: Force reinstall if app is already installed?
        :param message message: Message object to update with status
        """
        if self.installed and not force:
            return
        signals.emit("apps", "pre_install", self)
        # Get all apps that this app depends on and install them first
        deps = get_dependent(self.id, "install")
        if install_deps and deps:
            for x in deps:
                debug_str = "Installing {0} (dependency for {1})"
                logger.debug(debug_str.format(x, self.name))
                msg_str = "Installing dependencies for {0}... ({1})"
                message.update("info", msg_str.format(self.name, x))
                _install(x, load=load)
        # Install this app
        logger.debug("Installing {0}".format(self.name))
        message.update("info", "Installing {0}...".format(self.name))
        _install(self.id, load=load)
        ports = []
        for s in self.services:
            if s.get("default_policy", 0) and s["ports"]:
                ports.append(s["ports"])
        if ports and config.get("general", "enable_upnp", True):
            tracked_services.open_all_upnp(ports)
        verify_app_dependencies()
        signals.emit("apps", "post_install", self)

    def uninstall(self, force=False, message=DefaultMessage()):
        """
        Uninstall the arkOS application from the system.

        :param bool force: Uninstall the app even if others depend on it?
        :param message message: Message object to update with status
        """
        signals.emit("apps", "pre_remove", self)
        message.update("info", "Uninstalling application...")
        exclude = ["openssl", "openssh", "nginx", "python2", "git",
                   "nodejs", "npm"]

        # Make sure this app can be successfully removed, and if so also remove
        # any system-level packages that *only* this app requires
        for x in get(installed=True):
            for item in x.dependencies:
                if item["type"] == "app" and item["package"] == self.id \
                        and not force:
                    exc_str = "Cannot remove, {0} depends on this application"
                    raise Exception(exc_str.format(x.name))
                elif item["type"] == "system":
                    exclude.append(item["package"])

        # Stop any running services associated with this app
        for item in self.dependencies:
            if item["type"] == "system" and not item["package"] in exclude:
                if item.get("daemon"):
                    services.stop(item["daemon"])
                    services.disable(item["daemon"])
                pacman.remove([item["package"]],
                              purge=config.get("apps", "purge", False))
        logger.debug("Uninstalling {0}".format(self.name))

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
        ports = []
        for s in self.services:
            if s.get("default_policy", 0) and s["ports"]:
                ports.append(s["ports"])
        if ports and config.get("general", "enable_upnp", True):
            tracked_services.close_all_upnp(ports)
        signals.emit("apps", "post_remove", self)

    def ssl_enable(self, cert, sid=""):
        """
        Enable TLS on the selected application and service.

        The accompanying service ID is forwarded to the app-specific code to
        act as an identifier for which internal service is being specified.
        Ex. the XMPP plugin uses the domain name (xmpp.example.com) as ``sid``.

        :param Certificate cert: Certificate object to enable TLS with.
        :param str sid: ID for the associated app's service to enable TLS on.
        """
        signals.emit("apps", "pre_ssl_enable", self)
        if sid:
            d = self.ssl.ssl_enable(cert, sid)
        else:
            self.ssl.ssl_enable(cert)
        signals.emit("apps", "post_ssl_enable", self)
        return d

    def ssl_disable(self, sid=""):
        """
        Disable TLS on the selected application and service.

        :param str sid: ID for the associated app's service to disable TLS on.
        """
        signals.emit("apps", "pre_ssl_disable", self)
        if sid:
            self.ssl.ssl_disable(sid)
        else:
            self.ssl.ssl_disable()
        signals.emit("apps", "post_ssl_disable", self)

    def get_ssl_able(self):
        """
        Return list of application services that can support TLS.

        Example dict format:

            {"type": "app", "id": "xmpp_example.com", "aid": "xmpp",
              "sid": domain, "name": "Chat Server (example.com)"}

        :returns: List of TLS support dicts
        :rtype: list
        """
        return self.ssl.get_ssl_able()

    @property
    def as_dict(self):
        """Return app metadata as dict."""
        data = {}
        for x in self.__dict__:
            if not x.startswith("_") and x != "ssl":
                data[x] = self.__dict__[x]
        data["is_ready"] = True
        return data

    @property
    def serialized(self):
        """Return serializable app metadata as dict."""
        return self.as_dict


def get(id=None, type=None, loadable=None, installed=None,
        verify=True, force=False):
    """
    Retrieve arkOS application data from the system.

    If the cache is up and populated, applications are loaded from
    metadata stored there. If not (or ``force`` is set), the app directory is
    searched, modules are loaded and verified. This is used on first boot.

    :param str id: If present, obtain one app that matches this ID
    :param str type: Filter by ``app``, ``website``, ``database``, etc
    :param bool loadable: Filter by loadable (True) or not loadable (False)
    :param bool installed: Filter by installed (True) or uninstalled (False)
    :param bool verify: Verify app dependencies as the apps are scanned
    :param bool force: Force a rescan (do not rely on cache)
    :return: Application(s)
    :rtype: Application or list thereof
    """
    data = storage.apps.get("applications")
    if not data or force:
        data = scan(verify)
    if id or type or loadable or installed:
        type_list = []
        for x in data:
            if x.id == id and (x.loadable or not loadable):
                return x
            elif str(x.installed).lower() == str(installed).lower() \
                    and (x.type or not type):
                type_list.append(x)
            elif x.type == type and (x.loadable or not loadable):
                type_list.append(x)
        if type_list:
            return type_list
        return []
    return data


def scan(verify=True):
    """
    Search app directory for applications, load them and store metadata.

    Also contacts arkOS repo servers to obtain current list of available
    apps, and merges in any updates as necessary.

    :param bool verify: Verify app dependencies as the apps are scanned
    :return: list of Application objects
    :rtype: list
    """
    signals.emit("apps", "pre_scan")
    app_dir = config.get("apps", "app_dir")
    apps = []
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)

    # Get paths for installed apps, metadata for available ones
    installed_apps = [x for x in os.listdir(app_dir) if not x.startswith(".")]
    api_url = "https://{0}/api/v1/apps"
    available_apps = api(api_url.format(config.get("general", "repo_server")),
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
            warn_str = "Failed to load {0} due to a JSON parsing error"
            logger.warn(warn_str.format(x))
            continue
        except IOError:
            warn_str = "Failed to load {0}: manifest file inaccessible "\
                       "or not present"
            logger.warn(warn_str.format(x))
            continue
        logger.debug(" *** Loading {0}".format(data["id"]))
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
    """
    Verify that any dependent arkOS apps are properly installed/verified.

    Assigns ``loadable`` and ``error`` properties to all apps in the cache.
    """
    apps = [x for x in storage.apps.get("applications") if x.installed]
    for x in apps:
        for dep in x.dependencies:
            # For each app-type dependency in all installed apps...
            if dep["type"] == "app":
                # If the needed app isn't yet installed, put a fail message
                if not dep["package"] in [y.id for y in apps]:
                    x.loadable = False
                    x.error = "Depends on {0}, which is not installed"\
                              .format(dep["name"])
                    error_str = "*** Verify failed for {0} -- dependent on "\
                                "{1} which is not installed"
                    logger.debug(error_str.format(x.name, dep["name"]))
                    # Cascade this fail message to all apps in dependency chain
                    for z in get_dependent(x.id, "remove"):
                        z = storage.apps.get("applications", z)
                        z.loadable = False
                        error_str = "Depends on {0}, which cannot be loaded "\
                                    "because {1} is not installed"
                        z.error = error_str.format(x.name, dep["name"])
                # Also put fail msg if the app we depended on failed to load
                elif not storage.apps.get("applications", dep["package"])\
                        .loadable:
                    x.loadable = False
                    x.error = "Depends on {0}, which also failed"\
                              .format(dep["name"])
                    error_str = "*** Verify failed for {0} -- dependent on "\
                                "{1} which failed to load"
                    logger.debug(error_str.format(x.name, dep["name"]))
                    # Cascade this fail message to all apps in dependency chain
                    for z in get_dependent(x.id, "remove"):
                        z = storage.apps.get("applications", z)
                        z.loadable = False
                        error_str = "Depends on {0}, which cannot be loaded"\
                                    " because {1} failed to load"
                        z.error = error_str.format(x.name, dep["name"])


def get_dependent(id, op):
    """
    Return list of all apps to install or remove based on specified operation.

    :param str id: ID for arkOS app to check
    :param str op: ``install`` or ``remove``
    :returns: list of arkOS app IDs
    :rtype: list
    """
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
    """
    Utility function to download and install arkOS app packages.

    :param str id: ID of arkOS app to install
    :param bool load: Load the app after install?
    """
    app_dir = config.get("apps", "app_dir")
    # Download and extract the app source package
    api_url = "https://{0}/api/v1/apps/{1}"
    data = api(api_url.format(config.get("general", "repo_server"), id),
               returns="raw", crit=True)
    path = os.path.join(app_dir, "{0}.tar.gz".format(id))
    with open(path, "wb") as f:
        f.write(data)
    with tarfile.open(path, "r:gz") as t:
        t.extractall(app_dir)
    os.unlink(path)
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
