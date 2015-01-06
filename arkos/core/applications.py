import base64
import json
import os
import shutil
import tarfile

from distutils.spawn import find_executable

from arkos.core.frameworks import Framework
from arkos.core.system import packages
from arkos.core.languages import python
from arkos.core.utilities import api, dictfilter


class Apps(Framework):
    REQUIRES = ["services"]

    def on_init(self):
        self.app_dir = self.app.conf.get("apps", "app_dir")
        if not os.path.exists(self.app_dir):
            os.makedirs(self.app_dir)

    def get(self, reset=False, **kwargs):
        apps = []
        if self.app.storage:
            apps = self.app.storage.get_list("apps:installed")
        if not self.app.storage or not apps:
            apps = self.scan_apps()
            reset = True
        if self.app.storage and reset:
            apps = self.verify_all_dependencies(apps)
            self.app.storage.set_list("apps:installed", apps)
        return dictfilter(apps, kwargs)

    def get_available(self, reset=False, **kwargs):
        """
        apps = []
        if self.app.storage:
            apps = self.app.storage.get_list("apps:available")
        if not self.app.storage or not apps:
            apps = self.scan_available_apps()
            reset = True
        if self.app.storage and reset:
            self.app.storage.set_list("apps:available", apps)
        return dictfilter(apps, kwargs)
        """
        return []

    def get_updateable(self, reset=False, **kwargs):
        apps = []
        if self.app.storage:
            apps = self.app.storage.get_list("apps:updateable")
        if not self.app.storage or not apps:
            apps = self.scan_updateable_apps()
            reset = True
        if self.app.storage and reset:
            self.app.storage.set_list("apps:updateable", apps)
        return dictfilter(apps, kwargs)

    def scan_apps(self):
        apps = []
        applist = [app for app in os.listdir(self.app_dir) if not app.startswith(".")]
        applist = list(set(applist))

        while len(applist) > 0:
            app = applist[-1]
            try:
                self.app.logger.debug(" *** Scanning data for %s" % app)
                with open(os.path.join(self.app_dir, app, "manifest.json"), "r") as f:
                    data = json.loads(f.read())
            except Exception, e:
                self.app.logger.error("Failed to scan and import " % app)
                continue
            apps.append(data)
            applist.remove(app)
        return apps

    def scan_available_apps(self):
        return api('https://%s/' % self.app.conf.get("general", "repo_server"), 
            post={'get': 'list'}, returns='raw', crit=True)

    def scan_updateable_apps(self):
        upgradeable = []
        for x in self.get_available():
            for y in self.get_installed():
                if x["pid"] == y["pid"] and x["version"] != y["version"]:
                    upgradeable.append(x)
                    break
        return upgradeable

    def verify_system_dependencies(self, app):
        verify = True
        for dep in app["dependencies"]:
            if dep["type"] == "system":
                dep["verify"] = {}
                to_pacman = ""
                if dep["binary"] and not find_executable(dep["binary"]):
                    to_pacman = dep["package"]
                elif packages.is_installed(dep["package"]):
                    to_pacman = dep["package"]
                else:
                    dep["verify"]["status"] = "pass"
                if to_pacman:
                    try:
                        self.app.logger.debug(" *** Installing %s..." % to_pacman)
                        packages.install([to_pacman], query=True)
                    except Exception, e:
                        dep["verify"]["status"] = "fail"
                        dep["verify"]["info"] = str(e)
                        verify = False
                    finally:
                        if dep.has_key("internal") and dep["internal"]:
                            dep["verify"]["status"] = "fail"
                            dep["verify"]["info"] = "internal_restart"
                            verify = False
                        else:
                            dep["verify"]["status"] = "pass"
        return (verify, app)

    def verify_python_dependencies(self, app):
        verify = True
        for dep in app["dependencies"]:
            if dep["type"] == "python":
                dep["verify"] = {}
                to_pip = ""
                if dep["module"]:
                    try:
                        __import__(dep["module"])
                        dep["verify"]["status"] = "pass"
                    except ImportError:
                        to_pip = dep["package"]
                else:
                    if not python.is_installed(dep["package"]):
                        to_pip = dep["package"]
                    else:
                        dep["verify"]["status"] = "pass"
                if to_pip:
                    try:
                        self.app.logger.debug(" *** Installing %s (via pip)..." % dep["package"])
                        python.install([dep["package"]])
                    except Exception, e:
                        dep["verify"]["status"] = "fail"
                        dep["verify"]["info"] = str(e)
                        verify = False
                    finally:
                        if dep.has_key("internal") and dep["internal"]:
                            dep["verify"]["status"] = "fail"
                            dep["verify"]["info"] = "internal_restart"
                            verify = False
                        else:
                            dep["verify"]["status"] = "pass"
        return (verify, app)

    def verify_app_dependencies(self, apps):
        verified, disable = [], []
        for x in apps:
            for dep in x["dependencies"]:
                if dep["type"] == "app":
                    dep["verify"] = {}
                    if not dep["package"] in [y["pid"] for y in apps]:
                        dep["verify"]["status"] = "fail"
                        dep["verify"]["info"] = "not_installed"
                        x["verify"] = "fail"
                        self.app.logger.debug("*** Verify failed for %s -- %s app load failed" % (x["pid"],dep["package"]))
                        disable += [y["pid"] for y in self.verify_operation(x["pid"], "remove", apps, [])]
                    else:
                        if next(y for y in apps if y["pid"] == dep["package"])["verify"] == "pass":
                            dep["verify"]["status"] = "pass"
                        else:
                            dep["verify"]["status"] = "fail"
                            self.app.logger.debug("*** Verify failed for %s -- %s app load failed" % (x["pid"],dep["package"]))
                            disable += [y["pid"] for y in self.verify_operation(x["pid"], "remove", apps, [])]
            verified.append(x)
        disable = list(set(disable))
        for x in disable:
            for y in enumerate(verified):
                if x == y[1]["pid"]:
                    self.app.logger.debug("*** Verify failed for %s -- app load failed prior" % x)
                    verified[y[0]]["verify"] = "fail"
        return verified

    def verify_all_dependencies(self, apps):
        apps = list(apps)
        for app in enumerate(apps):
            rsp = self.verify_system_dependencies(app[1])
            if not rsp[0]:
                rsp[1]["verify"] = "fail"
            rsp = self.verify_python_dependencies(rsp[1])
            if not rsp[0]:
                rsp[1]["verify"] = "fail"
            apps[app[0]] = rsp[1]
        apps = self.verify_app_dependencies(apps)
        return apps

    def verify_operation(self, id, op, inst=[], avail=[]):
        metoo = []
        inst = inst or self.get()
        avail = avail or self.get_available()
        if op == 'remove':
            for i in inst:
                for dep in i["dependencies"]:
                    if dep['type'] == 'app' and dep['package'] == id:
                        metoo.append(('Remove', i))
                        metoo += self.verify_operation(i["pid"], 'remove', inst, avail)
        elif op == 'install':
            i = next(x for x in avail if x["pid"] == id)
            for dep in i["dependencies"]:
                if dep["type"] == 'app' and dep['package'] not in [x["pid"] for x in inst]:
                    metoo.append(('Install', dep['package']))
                    metoo += self.verify_operation(dep['package'], 'install', inst, avail)
        return metoo
    
    def install(self, ids):
        for x in ids:
            self._install_app(x)
        if self.app.storage:
            self.app.storage.get(reset=True)
            self.app.storage.get_updateable(reset=True)

    def _install_app(self, id):
        data = api('https://%s/' % self.app.conf.get("general", "repo_server"), 
            post={'get': 'plugin', 'id': id}, crit=True)
        if data['status'] == 200:
            with open(os.path.join(self.app_dir, 'plugin.tar.gz'), 'wb') as f:
                f.write(base64.b64decode(data['info']))
        else:
            raise Exception('Application retrieval failed - %s' % str(data['info']))
        with tarfile.open(os.path.join(self.app_dir, 'plugin.tar.gz'), 'r:gz') as t:
            t.extractall(self.app_dir)
        os.unlink(os.path.join(self.app_dir, 'plugin.tar.gz'))
        with open(os.path.join(self.app_dir, id, "manifest.json")) as f:
            data = json.loads(f.read())
    
    def remove(self, ids):
        for x in ids:
            self._remove_app(x)
        if self.app.storage:
            self.app.storage.get(reset=True)
            self.app.storage.get_updateable(reset=True)

    def _remove_app(self, id, force=False):
        purge = self.app.conf.get("apps", "purge", False)
        with open(os.path.join(self.app_dir, id, "manifest.json")) as f:
            data = json.loads(f.read())
        shutil.rmtree(os.path.join(self.app_dir, id))
        exclude = ['openssl', 'openssh', 'nginx', 'python2', 'redis', 'git']
        depends = []
        pdata = self.get()
        for item in data["dependencies"]:
            if item["type"] == "system":
                depends.append(item)
        for app in pdata:
            for item in app["dependencies"]:
                if item["type"] == "app" and item["package"] == id and not force:
                    raise Exception("Cannot remove, %s depends on this app" % item["package"])
                elif item["type"] == "system" and item["package"] in [x["package"] for x in depends]:
                    depends.remove(next(x for x in depends if x["package"] == item["package"]))
        for item in depends:
            if not item["package"] in exclude:
                if item["daemon"]:
                    self.services.stop(item["daemon"])
                    self.services.disable(item["daemon"])
                packages.remove([item["package"]], purge=purge)
