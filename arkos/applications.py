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

from arkos import config, logger, storage, signals, tracked_services
from arkos.messages import Notification, NotificationThread
from arkos.system import services
from arkos.languages import python, ruby
from arkos.utilities import api, compare_versions, errors


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

    def load(self, verify=True, cry=True, installed={}):
        """
        Load an application and associated metadata into the running process.

        :param bool verify: Verify System/Python/OS dependencies
        :param bool cry: Raise exception on dependency install failure?
        """
        try:
            signals.emit("apps", "pre_load", self)
            if verify:
                self.verify_dependencies(cry, installed)

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
                    if y[0] in [
                            "DatabaseManager", "Sharer", "Site",
                            "BackupController"]:
                        mgr = y[1]
                        break
                if module == "database":
                    for y in classes:
                        if issubclass(y[1], mgr) and y[1] != mgr:
                            setattr(self, "_database_mgr", y[1])
                elif module == "fileshare":
                    for y in classes:
                        if issubclass(y[1], mgr) and y[1] != mgr:
                            setattr(self, "_share_mgr", y[1])
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
            self.error = str(e)
            Notification(
                "warning", "Apps", "Could not load {0}: {1}".format(
                    self.name, self.error
                )
            ).send()

    def verify_dependencies(self, cry, installed):
        """
        Verify that the associated dependencies are all properly installed.

        Checks system-level packages, Python packages and arkOS Apps for
        installed status. Sets ``self.loadable`` with verify status and
        ``self.error`` with error message encountered on check.

        :returns: True if all verify checks passed
        :rtype: bool
        """
        verify, error = True, ""
        # If dependency isn't installed, add it to "to install" list
        # If it can't be installed, mark the app as not loadable and say why
        if not installed:
            pacman.refresh()
            installed["sys"] = pacman.get_installed()
            installed["py"] = python.get_installed()
            installed["py2"] = python.get_installed(py2=True)
            installed["rb"] = ruby.get_installed()
        for dep in self.dependencies:
            if dep["type"] == "system":
                pack = next(
                    filter(lambda x: x["id"] == dep["package"],
                           installed["sys"]),
                    None
                )
                invalid_ver = False
                if pack and dep.get("version"):
                    invalid_ver = compare_versions(
                        pack["version"], "lt", dep["version"]
                    )
                if not pack or invalid_ver:
                    logger.debug(
                        "Apps", "{0} not found. Attempting install..."
                        .format(dep["package"]))
                    try:
                        pacman.install(dep["package"])
                    except:
                        error = "Couldn't install {0}".format(dep["package"])
                        verify = False
                        if cry:
                            raise AppDependencyError(dep["package"], "system")
                    if dep.get("internal"):
                        error = "Reload required"
                        verify = False
            if dep["type"] == "python":
                pack = next(
                    filter(lambda x: x["id"].lower() == dep["package"].lower(),
                           installed["py"]),
                    None
                )
                invalid_ver = False
                if pack and dep.get("version"):
                    invalid_ver = compare_versions(
                        pack["version"], "lt", dep["version"]
                    )
                if not pack or invalid_ver:
                    logger.debug(
                        "Apps", "{0} not found. Attempting install..."
                        .format(dep["package"]))
                    try:
                        python.install(
                            dep["package"],
                            version=dep.get("version"),
                            py2=True if dep.get("py2") else False
                        )
                    except:
                        error = "Couldn't install {0}".format(dep["package"])
                        verify = False
                        if cry:
                            raise AppDependencyError(dep["package"], "python")
                    if dep.get("internal"):
                        error = "Reload required"
                        verify = False
            if dep["type"] == "ruby":
                pack = next(
                    filter(lambda x: x["id"] == dep["package"],
                           installed["rb"]),
                    None
                )
                invalid_ver = False
                if pack and dep.get("version"):
                    invalid_ver = compare_versions(
                        pack["version"], "lt", dep["version"]
                    )
                if not pack or invalid_ver:
                    logger.debug(
                        "Apps", "{0} not found. Attempting install..."
                        .format(dep["package"]))
                    try:
                        ruby.install(
                            dep["package"],
                            version=dep.get("version")
                        )
                    except:
                        error = "Couldn't install {0}".format(dep["package"])
                        verify = False
                        if cry:
                            raise AppDependencyError(dep["package"], "ruby")
                    if dep.get("internal"):
                        error = "Reload required"
                        verify = False
        self.loadable = verify
        self.error = error
        return verify

    def install(self, install_deps=True, load=True, force=False,
                cry=False, nthread=NotificationThread()):
        """
        Install the arkOS application to the system.

        :param bool install_deps: Install the app's dependencies too?
        :param bool load: Load the app after install?
        :param bool force: Force reinstall if app is already installed?
        :param bool cry: Raise exception on dependency install failure?
        :param NotificationThread nthread: notification thread to use
        """
        try:
            self._install(install_deps, load, force, cry, nthread)
        except Exception as e:
            nthread.complete(Notification("error", "Apps", str(e)))
            raise

    def _install(self, install_deps, load, force, cry, nthread):
        if self.installed and not force:
            return
        signals.emit("apps", "pre_install", self)
        # Get all apps that this app depends on and install them first
        deps = get_dependent(self.id, "install")
        if install_deps and deps:
            for x in deps:
                msg = "Installing dependencies for {0}... ({1})"
                nthread.update(
                    Notification("info", "Apps", msg.format(self.name, x))
                )
                _install(x, load=load, cry=cry)
        # Install this app
        msg = "Installing {0}...".format(self.name)
        nthread.update(Notification("info", "Apps", msg))
        _install(self.id, load=load, cry=cry)
        ports = []
        for s in self.services:
            if s.get("default_policy", 0) and s["ports"]:
                ports.append(s["ports"])
        if ports and config.get("general", "enable_upnp"):
            tracked_services.open_all_upnp(ports)
        verify_app_dependencies()
        smsg = "{0} installed successfully.".format(self.name)
        nthread.complete(Notification("success", "Apps", smsg))
        signals.emit("apps", "post_install", self)

    def uninstall(self, force=False, nthread=NotificationThread()):
        """
        Uninstall the arkOS application from the system.

        :param bool force: Uninstall the app even if others depend on it?
        :param NotificationThread nthread: notification thread to use
        """
        signals.emit("apps", "pre_remove", self)
        msg = "Uninstalling application..."
        nthread.update(Notification("info", "Apps", msg))
        exclude = ["openssl", "openssh", "nginx", "python2", "git",
                   "nodejs", "npm"]

        # Make sure this app can be successfully removed, and if so also remove
        # any system-level packages that *only* this app requires
        for x in get(installed=True):
            for item in x.dependencies:
                if item["type"] == "app" and item["package"] == self.id \
                        and not force:
                    exc_str = "{0} depends on this application"
                    raise errors.InvalidConfigError(exc_str.format(x.name))
                elif item["type"] == "system":
                    exclude.append(item["package"])

        # Stop any running services associated with this app
        for item in self.dependencies:
            if item["type"] == "system" and not item["package"] in exclude:
                if item.get("daemon"):
                    try:
                        services.get(item["daemon"]).stop()
                        services.get(item["daemon"]).disable()
                    except:
                        pass
                pacman.remove([item["package"]],
                              purge=config.get("apps", "purge"))

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
        if ports and config.get("general", "enable_upnp"):
            tracked_services.close_all_upnp(ports)
        smsg = "{0} uninstalled successfully".format(self.name)
        nthread.complete(Notification("success", "Apps", smsg))
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


class AppDependencyError(errors.Error):
    """Raised when an application dependency could not be installed."""

    def __init__(self, dep, dtype):
        self.dep = dep
        self.type = dtype

    def __str__(self):
        return "Could not install {1} app {0}".format(self.dep, self.type)


def get(id=None, type=None, loadable=None, installed=None,
        verify=True, force=False, cry=True):
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
    :param bool cry: Raise exception on dependency install failure?
    :return: Application(s)
    :rtype: Application or list thereof
    """
    data = storage.applications
    if not data or force:
        data = scan(verify, cry)
    if id:
        return data.get(id)
    if type:
        return filter(lambda x: x.type == type, data.values())
    if loadable:
        return filter(lambda x: x.loadable == loadable, data.values())
    if installed:
        return filter(lambda x: x.installed == installed, data.values())
    return data.values()


def scan(verify=True, cry=True):
    """
    Search app directory for applications, load them and store metadata.

    Also contacts arkOS repo servers to obtain current list of available
    apps, and merges in any updates as necessary.

    :param bool verify: Verify app dependencies as the apps are scanned
    :param bool cry: Raise exception on dependency install failure?
    :return: list of Application objects
    :rtype: list
    """
    signals.emit("apps", "pre_scan")
    logger.debug("Apps", "Scanning for applications")
    app_dir = config.get("apps", "app_dir")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)

    pacman.refresh()
    logger.debug("Apps", "Getting system/python/ruby installed list")
    inst_list = {
        "sys": pacman.get_installed(),
        "py": python.get_installed(),
        "py2": python.get_installed(py2=True),
        "rb": ruby.get_installed()
    }

    # Get paths for installed apps, metadata for available ones
    installed_apps = [x for x in os.listdir(app_dir) if not x.startswith(".")]
    api_url = ("https://{0}/api/v1/apps"
               .format(config.get("general", "repo_server")))
    logger.debug("Apps", "Fetching available apps: {0}".format(api_url))
    try:
        available_apps = api(api_url)
    except Exception as e:
        available_apps = []
        logger.error("Apps", "Could not get available apps from GRM.")
        logger.error("Apps", str(e))
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
            logger.warn("Apps", warn_str.format(x))
            continue
        except IOError:
            warn_str = "Failed to load {0}: manifest file inaccessible "\
                       "or not present"
            logger.warn("Apps", warn_str.format(x))
            continue
        logger.debug("Apps", " *** Loading {0}".format(data["id"]))
        app = App(**data)
        app.installed = True
        for y in enumerate(available_apps):
            if app.id == y[1]["id"] and app.version != y[1]["version"]:
                app.upgradable = y[1]["version"]
            if app.id == y[1]["id"]:
                app.assets = y[1]["assets"]
                available_apps[y[0]]["installed"] = True
        app.load(verify=verify, cry=cry, installed=inst_list)
        storage.applications[app.id] = app

    # Convert available apps payload to objects
    for x in available_apps:
        if not x.get("installed"):
            app = App(**x)
            app.installed = False
            storage.applications[app.id] = app

    if verify:
        verify_app_dependencies()
    signals.emit("apps", "post_scan")
    return storage.applications


def verify_app_dependencies():
    """
    Verify that any dependent arkOS apps are properly installed/verified.

    Assigns ``loadable`` and ``error`` properties to all apps in the cache.
    """
    for x in filter(lambda x: x.installed, storage.applications.values()):
        for dep in x.dependencies:
            # For each app-type dependency in all installed apps...
            if dep["type"] == "app":
                # If the needed app isn't yet installed, put a fail message
                pre_app = storage.applications.get(dep["package"])
                if not pre_app or not pre_app.installed:
                    x.loadable = False
                    x.error = "Depends on {0}, which is not installed"\
                              .format(dep["name"])
                    error_str = "*** Verify failed for {0} -- dependent on "\
                                "{1} which is not installed"
                    error_str = error_str.format(x.name, dep["name"])
                    logger.debug("Apps", error_str)
                    # Cascade this fail message to all apps in dependency chain
                    for z in get_dependent(x.id, "remove"):
                        z = storage.applications.get(z)
                        if not z:
                            continue
                        z.loadable = False
                        error_str = "Depends on {0}, which cannot be loaded "\
                                    "because {1} is not installed"
                        z.error = error_str.format(x.name, dep["name"])
                # Also put fail msg if the app we depended on failed to load
                elif not pre_app.loadable:
                    x.loadable = False
                    x.error = "Depends on {0}, which also failed"\
                              .format(dep["name"])
                    error_str = "*** Verify failed for {0} -- dependent on "\
                                "{1} which failed to load"
                    error_str = error_str.format(x.name, dep["name"])
                    logger.debug("Apps", error_str)
                    # Cascade this fail message to all apps in dependency chain
                    for z in get_dependent(x.id, "remove"):
                        z = storage.applications.get(z)
                        if not z:
                            continue
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
    # If any apps depend on me, flag them to be removed also
    if op == "remove":
        for app in storage.applications.values():
            for dep in app.dependencies:
                if dep["type"] == "app" and dep["package"] == id:
                    metoo.append(app)
                    metoo += get_dependent(app.id, "remove")
    # If I need any other apps to install, flag them to be installed also
    elif op == "install":
        app = storage.applications.get(id)
        for dep in filter(lambda x: x["type"] == "app", app.dependencies):
            pre_app = storage.applications.get(dep["package"])
            if not pre_app or not pre_app.installed:
                metoo.append(dep["package"])
                metoo += get_dependent(dep["package"], "install")
    return metoo


def _install(id, load=True, cry=True):
    """
    Utility function to download and install arkOS app packages.

    :param str id: ID of arkOS app to install
    :param bool load: Load the app after install?
    :param bool cry: Raise exception on dependency install failure?
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
    for x in app.services:
        if x.get("type") == "system" and x.get("binary") \
                and not x.get("ignore_on_install"):
            s = services.get(x["binary"])
            if s:
                s.enable()
                if s.state != "running":
                    try:
                        s.start()
                    except services.ActionError as e:
                        logger.warning(
                            "Apps", "{0} could not be automatically started."
                            .format(s.name))
    if load:
        app.load(cry=cry)
