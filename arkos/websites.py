import ConfigParser
import git
import os
import nginx
import re
import shutil

from arkos import applications, config, databases, signals, storage, tracked_services
from arkos.languages import php
from arkos.system import users, groups, services
from arkos.utilities import download, shell, random_string, DefaultMessage


# If no cipher preferences set, use the default ones
# As per Mozilla recommendations, but substituting 3DES for RC4
ciphers = ":".join([
    "ECDHE-RSA-AES128-GCM-SHA256", "ECDHE-ECDSA-AES128-GCM-SHA256",
    "ECDHE-RSA-AES256-GCM-SHA384", "ECDHE-ECDSA-AES256-GCM-SHA384",
    "kEDH+AESGCM", "ECDHE-RSA-AES128-SHA256",
    "ECDHE-ECDSA-AES128-SHA256", "ECDHE-RSA-AES128-SHA",
    "ECDHE-ECDSA-AES128-SHA", "ECDHE-RSA-AES256-SHA384",
    "ECDHE-ECDSA-AES256-SHA384", "ECDHE-RSA-AES256-SHA",
    "ECDHE-ECDSA-AES256-SHA", "DHE-RSA-AES128-SHA256",
    "DHE-RSA-AES128-SHA", "DHE-RSA-AES256-SHA256",
    "DHE-DSS-AES256-SHA", "AES128-GCM-SHA256", "AES256-GCM-SHA384",
    "ECDHE-RSA-DES-CBC3-SHA", "ECDHE-ECDSA-DES-CBC3-SHA",
    "EDH-RSA-DES-CBC3-SHA", "EDH-DSS-DES-CBC3-SHA",
    "DES-CBC3-SHA", "HIGH", "!aNULL", "!eNULL", "!EXPORT", "!DES",
    "!RC4", "!MD5", "!PSK"
    ])


class Site:
    def __init__(
            self, id="", addr="", port=80, path="", php=False, version="",
            cert=None, db=None, data_path="", block=[], enabled=False):
        self.id = id
        self.path = path.encode("utf-8")
        self.addr = addr
        self.port = port
        self.php = php
        self.version = version
        self.cert = None
        self.db = None
        self.meta = None
        self.enabled = enabled
        self.data_path = data_path
        if hasattr(self, "addtoblock") and self.addtoblock and block:
            self.addtoblock += block
        elif block:
            self.addtoblock = block

    def install(self, meta, extra_vars={}, enable=True, message=DefaultMessage()):
        message.update("info", "Preparing to install...", head="Installing website")

        # Make sure the chosen port is indeed open
        if not tracked_services.is_open_port(self.port, self.addr):
            raise Exception("This port is taken by another site or service, please choose another")

        # Set some metadata values
        specialmsg, dbpasswd = "", ""
        site_dir = config.get("websites", "site_dir")
        self.meta = meta
        self.path = self.path.encode("utf-8") or os.path.join(site_dir, self.id).encode("utf-8")
        self.php = extra_vars.get("php") or self.php or self.meta.uses_php or False
        self.version = self.meta.version.rsplit("-", 1)[0] if self.meta.website_updates else None

        # Classify the source package type
        if not self.meta.download_url:
            ending = ""
        elif self.meta.download_url.endswith(".tar.gz"):
            ending = ".tar.gz"
        elif self.meta.download_url.endswith(".tgz"):
            ending = ".tgz"
        elif self.meta.download_url.endswith(".tar.bz2"):
            ending = ".tar.bz2"
        elif self.meta.download_url.endswith(".zip"):
            ending = ".zip"
        elif self.meta.download_url.endswith(".git"):
            ending = ".git"
        else:
            raise Exception("Only GIT repos, gzip, bzip, and zip packages supported for now")

        message.update("info", "Running pre-installation...", head="Installing website")

        # Call website type's pre-install hook
        try:
            self.pre_install(extra_vars)
        except Exception, e:
            raise Exception("Error during website config - "+str(e))

        # If needs DB and user didn't select an engine, choose one for them
        if len(self.meta.database_engines) > 1 and extra_vars.get("dbengine", None):
            self.meta.selected_dbengine = extra_vars.get("dbengine")
        if (not hasattr(self.meta, "selected_dbengine") or not self.meta.selected_dbengine) \
                and self.meta.database_engines:
            self.meta.selected_dbengine = self.meta.database_engines[0]

        # Create DB and/or DB user as necessary
        if hasattr(self.meta, "selected_dbengine") and self.meta.selected_dbengine:
            message.update("info", "Creating database...", head="Installing website")
            try:
                mgr = databases.get_managers(self.meta.selected_dbengine)
                if not mgr:
                    raise Exception("No manager found for %s" % self.meta.selected_dbengine)
                # Make sure DB daemon is running if it has one
                if not mgr.state:
                    svc = services.get(mgr.meta.database_service)
                    svc.restart()
                self.db = mgr.add_db(self.id)
                # If multiuser DB type, create user
                if mgr.meta.database_multiuser:
                    dbpasswd = random_string()[0:16]
                    db_user = mgr.add_user(self.id, dbpasswd)
                    db_user.chperm("grant", self.db)
            except Exception, e:
                raise Exception("Database could not be created - %s" % str(e))

        # Make sure the target directory exists, but is empty
        pkg_path = "/tmp/"+self.id+ending
        if os.path.isdir(self.path):
            shutil.rmtree(self.path)
        os.makedirs(self.path)

        # Download and extract the source repo / package
        message.update("info", "Downloading website source...", head="Installing website")
        if self.meta.download_url and ending == ".git":
            git.Repo.clone_from(self.meta.download_url, self.path)
        elif self.meta.download_url:
            try:
                download(self.meta.download_url, file=pkg_path, crit=True)
            except Exception, e:
                raise Exception("Couldn't download - %s" % str(e))

            # Format extraction command according to type
            message.update("info", "Extracting source...", head="Installing website")
            if ending in [".tar.gz", ".tgz", ".tar.bz2"]:
                extract_cmd = "tar "
                extract_cmd += "xzf" if ending in [".tar.gz", ".tgz"] else "xjf"
                extract_cmd += " /tmp/%s -C %s --strip 1" % (self.id+ending, self.path)
            else:
                extract_cmd = "unzip -d %s /tmp/%s" % (self.path, self.id+ending)
            status = shell(extract_cmd)
            if status["code"] >= 1:
                raise Exception(status["stderr"])
            os.remove(pkg_path)

        # Set proper starting permissions on source directory
        uid, gid = users.get_system("http").uid, groups.get_system("http").gid
        os.chmod(self.path, 0755)
        os.chown(self.path, uid, gid)
        for r, d, f in os.walk(self.path):
            for x in d:
                os.chmod(os.path.join(r, x), 0755)
                os.chown(os.path.join(r, x), uid, gid)
            for x in f:
                os.chmod(os.path.join(r, x), 0644)
                os.chown(os.path.join(r, x), uid, gid)

        # If there is a custom path for the data directory, set it up
        if hasattr(self.meta, "website_datapaths") and self.meta.website_datapaths \
                and extra_vars.get("datadir"):
            self.data_path = extra_vars["datadir"]
            if not os.path.exists(self.data_path):
                os.makedirs(self.data_path)
            os.chmod(self.data_path, 0755)
            os.chown(self.data_path, uid, gid)
        elif hasattr(self, "website_default_data_subdir"):
            self.data_path = os.path.join(self.path, self.website_default_data_subdir)
        else:
            self.data_path = self.path

        # Create the nginx serverblock
        addtoblock = self.addtoblock or []
        if extra_vars.get("addtoblock"):
            addtoblock += nginx.loads(extra_vars.get("addtoblock"), False)
        try:
            block = nginx.Conf()
            server = nginx.Server(
                nginx.Key("listen", str(self.port)),
                nginx.Key("server_name", self.addr),
                nginx.Key("root", self.path),
                nginx.Key("index", "index."+("php" if self.php else "html"))
            )
            if addtoblock:
                server.add(*[x for x in addtoblock])
            block.add(server)
            nginx.dumpf(block, os.path.join("/etc/nginx/sites-available", self.id))
        except Exception, e:
            raise Exception("nginx serverblock couldn't be written - "+str(e))

        # Create arkOS metadata file
        meta = ConfigParser.SafeConfigParser()
        meta.add_section("website")
        meta.set("website", "id", self.id)
        meta.set("website", "type", self.meta.id)
        meta.set("website", "ssl", self.cert.id if hasattr(self, "cert") and self.cert else "None")
        meta.set("website", "version", self.version or "None")
        if hasattr(self.meta, "website_datapaths") and self.meta.website_datapaths \
                and self.data_path:
            meta.set("website", "data_path", self.data_path)
        meta.set("website", "dbengine", "")
        if hasattr(self.meta, "selected_dbengine"):
            meta.set("website", "dbengine", self.meta.selected_dbengine or "")
        with open(os.path.join(self.path, ".arkos"), "w") as f:
            meta.write(f)

        # Call site type's post-installation hook
        message.update("info", "Running post-installation. This may take a few minutes...",
            head="Installing website")
        try:
            specialmsg = self.post_install(extra_vars, dbpasswd)
        except Exception, e:
            shutil.rmtree(self.path, True)
            if self.db:
                self.db.remove()
                db_user = databases.get_user(self.id)
                if db_user:
                    db_user.remove()
            os.unlink(os.path.join("/etc/nginx/sites-available", self.id))
            raise Exception("Error during website config - "+str(e))

        # Cleanup and reload daemons
        message.update("info", "Finishing...", head="Installing website")
        self.installed = True
        storage.sites.add("sites", self)
        signals.emit("websites", "site_installed", self)
        if enable:
            self.nginx_enable()
        if enable and self.php:
            php.open_basedir("add", "/srv/http/")
            php_reload()
        if specialmsg:
            return specialmsg

    def ssl_enable(self):
        # Get server-preferred ciphers
        if config.get("certificates", "ciphers"):
            ciphers = config.get("certificates", "ciphers")
        else:
            config.set("certificates", "ciphers", ciphers)
            config.save()

        block = nginx.loadf(os.path.join("/etc/nginx/sites-available/", self.id))

        # If the site is on port 80, setup an HTTP redirect to new port 443
        server = block.servers[0]
        listen = server.filter("Key", "listen")[0]
        if listen.value == "80":
            listen.value = "443 ssl"
            block.add(nginx.Server(
                nginx.Key("listen", "80"),
                nginx.Key("server_name", self.addr),
                nginx.Key("return", "301 https://%s$request_uri" % self.addr)
            ))
            for x in block.servers:
                if x.filter("Key", "listen")[0].value == "443 ssl":
                    server = x
                    break
        else:
            listen.value = listen.value.split(" ssl")[0] + " ssl"

        # Clean up any pre-existing SSL directives that no longer apply
        for x in server.all():
            if type(x) == nginx.Key and x.name.startswith("ssl_"):
                server.remove(x)

        # Add the necessary SSL directives to the serverblock and save
        server.add(
            nginx.Key("ssl_certificate", self.cert.cert_path),
            nginx.Key("ssl_certificate_key", self.cert.key_path),
            nginx.Key("ssl_protocols", "TLSv1 TLSv1.1 TLSv1.2"),
            nginx.Key("ssl_ciphers", ciphers),
            nginx.Key("ssl_session_timeout", "5m"),
            nginx.Key("ssl_prefer_server_ciphers", "on"),
            nginx.Key("ssl_dhparam", "/etc/arkos/ssl/dh_params.pem"),
            nginx.Key("ssl_session_cache", "shared:SSL:50m"),
            )
        nginx.dumpf(block, os.path.join("/etc/nginx/sites-available/", self.id))

        # Set the certificate name in the metadata file
        meta = ConfigParser.SafeConfigParser()
        meta.read(os.path.join(self.path, ".arkos"))
        meta.set("website", "ssl", self.cert.id)
        with open(os.path.join(self.path, ".arkos"), "w") as f:
            meta.write(f)

        # Call the website type's SSL enable hook
        self.enable_ssl(self.cert.cert_path, self.cert.key_path)

    def ssl_disable(self):
        block = nginx.loadf(os.path.join("/etc/nginx/sites-available/", self.id))

        # If there's an 80-to-443 redirect block, get rid of it
        if len(block.servers) > 1:
            for x in block.servers:
                if not "ssl" in x.filter("Key", "listen")[0].value \
                and x.filter("key", "return"):
                    block.remove(x)
                    break

        # Remove all SSL directives and save
        server = block.servers[0]
        listen = server.filter("Key", "listen")[0]
        if listen.value == "443 ssl":
            listen.value = "80"
        else:
            listen.value = listen.value.rstrip(" ssl")
        server.remove(*[x for x in server.filter("Key") if x.name.startswith("ssl_")])
        nginx.dumpf(block, os.path.join("/etc/nginx/sites-available/", self.id))
        meta = ConfigParser.SafeConfigParser()
        meta.read(os.path.join(self.path, ".arkos"))
        meta.set("website", "ssl", "None")
        with open(os.path.join(self.path, ".arkos"), "w") as f:
            meta.write(f)

        # Call the website type's SSL disable hook
        self.disable_ssl()

    def nginx_enable(self, reload=True):
        origin = os.path.join("/etc/nginx/sites-available", self.id)
        target = os.path.join("/etc/nginx/sites-enabled", self.id)
        if not os.path.exists(target):
            os.symlink(origin, target)
            self.enabled = True
        if reload == True:
            return nginx_reload()
        return True

    def nginx_disable(self, reload=True):
        try:
            os.unlink(os.path.join("/etc/nginx/sites-enabled", self.id))
        except:
            pass
        self.enabled = False
        if reload == True:
            return nginx_reload()
        return True

    def edit(self, newname=""):
        site_dir = config.get("websites", "site_dir")
        block = nginx.loadf(os.path.join("/etc/nginx/sites-available", self.id))

        # If SSL is enabled and the port is changing to 443, create the port 80 redirect
        server = block.servers[0]
        if self.cert and self.port == 443:
            for x in block.servers:
                if x.filter("Key", "listen")[0].value == "443 ssl":
                    server = x
            if self.port != 443:
                for x in block.servers:
                    if not "ssl" in x.filter("Key", "listen")[0].value \
                    and x.filter("key", "return"):
                        block.remove(x)
        elif self.port == 443:
            block.add(nginx.Server(
                nginx.Key("listen", "80"),
                nginx.Key("server_name", self.addr),
                nginx.Key("return", "301 https://%s$request_uri"%self.addr)
            ))

        # If the name was changed...
        if newname and self.id != newname:
            # rename the folder and files...
            if self.path.endswith("_site"):
                self.path = os.path.join(site_dir, newname, "_site")
            elif self.path.endswith("htdocs"):
                self.path = os.path.join(site_dir, newname, "htdocs")
            else:
                self.path = os.path.join(site_dir, newname)
            self.path = self.path.encode("utf-8")
            if os.path.exists(self.path):
                shutil.rmtree(self.path)
            self.nginx_disable(reload=False)
            shutil.move(os.path.join(site_dir, self.id), self.path)
            os.unlink(os.path.join("/etc/nginx/sites-available", self.id))
            signals.emit("websites", "site_removed", self)
            self.id = newname

            # then update the site's arkOS metadata file with the new name
            meta = ConfigParser.SafeConfigParser()
            meta.read(os.path.join(self.path, ".arkos"))
            meta.set("website", "id", self.id)
            with open(os.path.join(self.path, ".arkos"), "w") as f:
                meta.write(f)
            self.nginx_enable(reload=False)

        # Pass any necessary updates to the nginx serverblock and save
        server.filter("Key", "listen")[0].value = str(self.port)+" ssl" if self.cert else str(self.port)
        server.filter("Key", "server_name")[0].value = self.addr
        server.filter("Key", "root")[0].value = self.path
        server.filter("Key", "index")[0].value = "index.php" if hasattr(self, "php") and self.php else "index.html"
        nginx.dumpf(block, os.path.join("/etc/nginx/sites-available", self.id))

        # Call the site's edited hook, if it has one, then reload nginx
        signals.emit("websites", "site_loaded", self)
        if hasattr(self, "site_edited"):
            self.site_edited()
        nginx_reload()

    def update(self, message=DefaultMessage()):
        if self.version == self.meta.version.rsplit("-", 1)[0]:
            raise Exception("Website is already at the latest version")
        elif self.version in [None, "None"]:
            raise Exception("Updates not supported for this website type")

        # Classify the source package type
        if not self.meta.download_url:
            ending = ""
        elif self.meta.download_url.endswith(".tar.gz"):
            ending = ".tar.gz"
        elif self.meta.download_url.endswith(".tgz"):
            ending = ".tgz"
        elif self.meta.download_url.endswith(".tar.bz2"):
            ending = ".tar.bz2"
        elif self.meta.download_url.endswith(".zip"):
            ending = ".zip"
        elif self.meta.download_url.endswith(".git"):
            ending = ".git"
        else:
            raise Exception("Only GIT repos, gzip, bzip, and zip packages supported for now")

        # Download and extract the source package
        message.update("info", "Downloading website source...", head="Updating website")
        if self.download_url and ending == ".git":
            pkg_path = self.download_url
        elif self.download_url:
            pkg_path = os.path.join("/tmp", self.id+ending)
            try:
                download(self.meta.download_url, file=pkg_path, crit=True)
            except Exception, e:
                raise Exception("Couldn't update - %s" % str(e))

        # Call the site type's update hook
        try:
            message.update("info", "Updating website...", head="Updating website")
            self.update_site(self.path, pkg_path, self.version)
        except Exception, e:
            raise Exception("Couldn't update - %s" % str(e))
        finally:
            # Update stored version and remove temp source archive
            self.version = self.meta.version.rsplit("-", 1)[0]
            if pkg_path:
                os.unlink(pkg_path)

    def remove(self, message=DefaultMessage()):
        # Call site type's pre-removal hook
        message.update("info", "Running pre-removal...", head="Removing website")
        self.pre_remove()

        # Remove source directories
        message.update("info", "Removing website...", head="Removing website")
        if self.path.endswith("_site"):
            shutil.rmtree(self.path.split("/_site")[0])
        elif self.path.endswith("htdocs"):
            shutil.rmtree(self.path.split("/htdocs")[0])
        elif os.path.islink(self.path):
            os.unlink(self.path)
        else:
            shutil.rmtree(self.path)

        # If there's a database, get rid of that too
        if self.db:
            message.update("info", "Removing database...", head="Removing website")
            if self.db.manager.meta.database_multiuser:
                db_user = databases.get_user(self.db.id)
                if db_user:
                    db_user.remove()
            self.db.remove()

        self.nginx_disable(reload=True)
        try:
            os.unlink(os.path.join("/etc/nginx/sites-available", self.id))
        except:
            pass

        # Call site type's post-removal hook
        message.update("info", "Running post-removal...", head="Removing website")
        self.post_remove()
        storage.sites.remove("sites", self)
        signals.emit("websites", "site_removed", self)

    @property
    def as_dict(self):
        return {
            "id": self.id,
            "path": self.path,
            "addr": self.addr,
            "port": self.port,
            "site_type": self.meta.id,
            "site_name": self.meta.name,
            "site_icon": self.meta.icon,
            "version": self.version,
            "certificate": self.cert.id if self.cert else None,
            "database": self.db.id if self.db else None,
            "php": self.php,
            "enabled": self.enabled,
            "has_actions": self.meta.website_extra_actions if hasattr(self.meta, "website_extra_actions") else None,
            "is_ready": True
        }

    @property
    def serialized(self):
        return self.as_dict


class ReverseProxy(Site):
    def __init__(
            self, id="", name="", path="", addr="", port=80,
            base_path="", block=[], type="internal"):
        self.id = id
        self.name = name
        self.addr = addr
        self.path = path.encode("utf-8")
        self.port = port
        self.base_path = base_path
        self.block = block
        self.type = type
        self.cert = None
        self.installed = False

    def install(self, extra_vars={}, enable=True, message=None):
        # Set metadata values
        site_dir = config.get("websites", "site_dir")
        self.path = self.path.encode("utf-8") or os.path.join(site_dir, self.id).encode("utf-8")

        try:
            os.makedirs(self.path)
        except:
            pass

        # If extra data is passed in, set up the serverblock accordingly
        if extra_vars:
			if not extra_vars.get("type") or not extra_vars.get("pass"):
				raise Exception("Must enter ReverseProxy type and location to pass to")
			elif extra_vars.get("type") in ["fastcgi", "uwsgi"]:
				self.block = [nginx.Location(extra_vars.get("lregex", "/"),
					nginx.Key("%s_pass"%extra_vars.get("type"),
						"%s"%extra_vars.get("pass")),
					nginx.Key("include", "%s_params"%extra_vars.get("type"))
					)]
			else:
				self.block = [nginx.Location(extra_vars.get("lregex", "/"),
					nginx.Key("proxy_pass", "%s"%extra_vars.get("pass")),
					nginx.Key("proxy_redirect", "off"),
					nginx.Key("proxy_buffering", "off"),
					nginx.Key("proxy_set_header", "Host $host")
					)]
			if extra_vars.get("xrip"):
				self.block[0].add(nginx.Key("proxy_set_header", "X-Real-IP $remote_addr"))
			if extra_vars.get("xff") == "1":
				self.block[0].add(nginx.Key("proxy_set_header", "X-Forwarded-For $proxy_add_x_forwarded_for"))

        # Create the nginx serverblock and arkOS metadata files
        block = nginx.Conf()
        server = nginx.Server(
            nginx.Key("listen", self.port),
            nginx.Key("server_name", self.addr),
            nginx.Key("root", self.base_path or self.path),
        )
        server.add(*[x for x in self.block])
        block.add(server)
        nginx.dumpf(block, os.path.join("/etc/nginx/sites-available", self.id))
        meta = ConfigParser.SafeConfigParser()
        meta.add_section("website")
        meta.set("website", "id", self.id)
        meta.set("website", "name", self.name)
        meta.set("website", "type", "ReverseProxy")
        meta.set("website", "extra", self.type)
        meta.set("website", "version", "None")
        meta.set("website", "ssl", self.cert.id if hasattr(self, "cert") and self.cert else "None")
        with open(os.path.join(self.path, ".arkos"), "w") as f:
            meta.write(f)

        # Track port and reload daemon
        self.meta = None
        self.installed = True
        storage.sites.add("sites", self)
        signals.emit("websites", "site_installed", self)
        self.nginx_enable()

    def remove(self, message=None):
        shutil.rmtree(self.path)
        self.nginx_disable(reload=True)
        try:
            os.unlink(os.path.join("/etc/nginx/sites-available", self.id))
        except:
            pass
        storage.sites.remove("sites", self)
        signals.emit("websites", "site_removed", self)

    @property
    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "addr": self.addr,
            "port": self.port,
            "site_name": "Reverse Proxy",
            "site_type": self.type,
            "site_icon": "fa fa-globe",
            "version": None,
            "certificate": self.cert.id if self.cert else None,
            "database": None,
            "php": False,
            "enabled": self.enabled,
            "is_ready": True
        }

    @property
    def serialized(self):
        return self.as_dict


def get(id=None, type=None, verify=True):
    sites = storage.sites.get("sites")
    if not sites:
        sites = scan()
    if id or type:
        type_list = []
        for site in sites:
            if site.id == id:
                return site
            elif (type and (type == "ReverseProxy" and isinstance(site, ReverseProxy))) \
            or (type and site.meta.id == type):
                type_list.append(site)
        if type_list:
            return type_list
        return None
    return sites

def scan():
    from arkos import certificates
    sites = []

    for x in os.listdir("/etc/nginx/sites-available"):
        path = os.path.join("/srv/http/webapps", x)
        if not os.path.exists(path):
            continue

        # Read metadata
        meta = ConfigParser.SafeConfigParser()
        if not meta.read(os.path.join(path, ".arkos")):
            continue

        # Create the proper type of website object
        site_type = meta.get("website", "type")
        if site_type != "ReverseProxy":
            # If it's a regular website, initialize its class, metadata, etc
            app = applications.get(site_type)
            if not app or not app.loadable or not app.installed:
                continue
            site = app._website(id=meta.get("website", "id"))
            site.meta = app
            site.data_path = meta.get("website", "data_path", "") \
                if meta.has_option("website", "data_path") else ""
            site.db = databases.get(site.id) \
                if meta.has_option("website", "dbengine") else None
        else:
            # If it's a reverse proxy, follow a simplified procedure
            site = ReverseProxy(id=meta.get("website", "id"))
            site.name = meta.get("website", "name")
            site.type = meta.get("website", "extra")
            site.meta = None
        certname = meta.get("website", "ssl", "None")
        site.cert = certificates.get(certname) if certname != "None" else None
        if site.cert:
            site.cert.assigns.append({
                "type": "website", "id": site.id,
                "name": site.id if site.meta else site.name
            })
        site.version = meta.get("website", "version", None)
        site.enabled = os.path.exists(os.path.join("/etc/nginx/sites-enabled", x))
        site.installed = True

        # Load the proper nginx serverblock and get more data
        try:
            ssl = None
            block = nginx.loadf(os.path.join("/etc/nginx/sites-available", x))
            for y in block.servers:
                if "ssl" in y.filter("Key", "listen")[0].value:
                    site.ssl = True
                    server = y
                    break
            else:
                server = block.servers[0]
            port_regex = re.compile("(\\d+)\s*(.*)")
            site.port = int(re.match(port_regex, server.filter("Key", "listen")[0].value).group(1))
            site.addr = server.filter("Key", "server_name")[0].value
            site.path = server.filter("Key", "root")[0].value
            site.php = "php" in server.filter("Key", "index")[0].value
        except IndexError:
            pass
        sites.append(site)
        signals.emit("websites", "site_loaded", site)

    storage.sites.set("sites", sites)
    return sites

def nginx_reload():
    try:
        s = services.get("nginx")
        s.restart()
        return True
    except services.ActionError:
        return False

def php_reload():
    try:
        s = services.get("php-fpm")
        s.restart()
    except services.ActionError:
        pass
