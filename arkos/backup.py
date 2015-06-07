import ConfigParser
import glob
import json
import os
import shutil
import StringIO
import tarfile

from arkos import version as arkos_version
from arkos import secrets, config, signals, applications, websites
from arkos.system import systemtime
from arkos.utilities import random_string, shell


class BackupController:
    def __init__(self, id, icon, site=None, version=None):
        self.id = id
        self.icon = icon
        self.ctype = "site" if site else "app"
        self.site = site
        self.version = version

    def _get_config(self):
        configs = []
        if self.ctype == "site":
            configs += self.get_config(self.site)
        else:
            configs += self.get_config()
        return configs

    def _get_data(self):
        data = []
        if self.ctype == "site":
            data += self.get_data(self.site)
            data.append("/etc/nginx/sites-available/%s" % self.site.id)
            data.append(self.site.path)
        else:
            data += self.get_data()
        return data

    def backup(self, data=True, backup_location=""):
        if not backup_location:
            backup_location = config.get("backups", "location", "/var/lib/arkos/backups")
        if self.ctype == "site":
            self.version = self.site.meta.version
        signals.emit("backups", "pre_backup", self)

        # Trigger the pre-backup hook for the app/site
        if self.ctype == "site":
            self.pre_backup(self.site)
        else:
            self.pre_backup()

        # Create backup directory in storage
        backup_dir = os.path.join(backup_location, self.id)
        try:
            os.makedirs(backup_dir)
        except:
            pass

        # Gather config and data file paths to archive
        myconfig = self._get_config()
        data = self._get_data() if data else []
        timestamp = systemtime.get_serial_time()
        isotime = systemtime.get_iso_time(timestamp)
        path = os.path.join(backup_dir, "%s-%s.tar.gz" % (self.id,timestamp))
        # Zip up the gathered file paths
        with tarfile.open(path, "w:gz") as t:
            for f in myconfig+data:
                for x in glob.glob(f):
                    t.add(x)
            if self.ctype == "site" and self.site.db:
                dbsql = StringIO.StringIO(self.site.db.dump())
                dinfo = tarfile.TarInfo(name="/%s.sql"%self.site.id)
                dinfo.size = len(dbsql.buf)
                t.addfile(tarinfo=dinfo, fileobj=dbsql)
        # Create a metadata file to track information
        info = {"pid": self.id, "type": self.ctype, "icon": self.icon,
            "version": self.version, "time": isotime}
        if self.site:
            info["site_type"] = self.site.meta.id
        with open(os.path.join(backup_dir, "%s-%s.meta" % (self.id,timestamp)), "w") as f:
            f.write(json.dumps(info))

        # Trigger post-backup hook for the app/site
        if self.ctype == "site":
            self.post_backup(self.site)
        else:
            self.post_backup()
        signals.emit("backups", "post_backup", self)

        return {"id": self.id+"/"+timestamp, "pid": self.id, "path": path,
            "icon": self.icon, "type": self.ctype, "time": isotime,
            "version": self.version, "size": os.path.getsize(path),
            "site_type": self.site.meta.id if self.site else None, "is_ready": True}

    def restore(self, data):
        signals.emit("backups", "pre_restore", self)
        # Trigger pre-restore hook for the app/site
        self.pre_restore()

        # Extract all files in archive
        sitename = ""
        with tarfile.open(data["path"], "r:gz") as t:
            for x in t.getnames():
                if x.startswith("etc/nginx/sites-available"):
                    sitename = os.path.basename(x)
            t.extractall("/")

        # If it's a website that had a database, restore DB via SQL file too
        dbpasswd = ""
        if self.ctype == "site" and sitename:
            self.site = websites.get(sitename)
            if not self.site:
                websites.scan()
                self.site = websites.get(sitename)
            meta = ConfigParser.SafeConfigParser()
            meta.read(os.path.join(self.site.path, ".arkos"))
            if meta.get("website", "dbengine", None) and os.path.exists("/%s.sql"%sitename):
                dbmgr = databases.get_managers(meta.get("website", "dbengine"))
                if databases.get(sitename):
                    databases.get(sitename).remove()
                db = dbmgr.add_db(sitename)
                with open("/%s.sql"%sitename, "r") as f:
                    db.execute(f.read())
                os.unlink("/%s.sql"%sitename)
                if dbmgr.meta.database_multiuser:
                    dbpasswd = random_string()[0:16]
                    if databases.get_user(sitename):
                        databases.get_user(sitename).remove()
                    db_user = dbmgr.add_user(sitename, dbpasswd)
                    db_user.chperm("grant", db)

        # Trigger post-restore hook for the app/site
        if self.ctype == "site":
            self.post_restore(self.site, dbpasswd)
            self.site.nginx_enable()
        else:
            self.post_restore()
        signals.emit("backups", "post_restore", self)
        data["is_ready"] = True
        return data

    def get_config(self):
        return []

    def get_data(self):
        return []

    def pre_backup(self):
        pass

    def post_backup(self):
        pass

    def pre_restore(self):
        pass

    def post_restore(self):
        pass


class arkOSBackupCfg(BackupController):
    def get_config(self):
        return ["/etc/arkos", "/tmp/ldap.ldif"]

    def get_data(self):
        return []

    def pre_backup(self):
        s = shell("slapcat -n 1")
        if s["code"] != 0:
            raise Exception("Could not backup LDAP database. Please check logs for errors.")
        with open("/tmp/ldap.ldif", "w") as f:
            f.write(s["stdout"])

    def post_backup(self):
        if os.path.exists("/tmp/ldap.ldif"):
            os.unlink("/tmp/ldap.ldif")

    def post_restore(self):
        if not os.path.exists("/tmp/ldap.ldif"):
            raise Exception("Could not restore LDAP database. Please check logs for errors.")
        with open("/tmp/ldap.ldif", "r") as f:
            ldif = f.read()
        s = shell('ldapadd -D "cn=admin,dc=arkos-servers,dc=org" -w %s' % secrets.get("ldap"),
            stdin=ldif)
        if os.path.exists("/tmp/ldap.ldif"):
            os.unlink("/tmp/ldap.ldif")
        if s["code"] != 0:
            raise Exception("Could not restore LDAP database. Please check logs for errors.")


def get(backup_location=""):
    backups = []
    if not backup_location:
        backup_location = config.get("backups", "location", "/var/lib/arkos/backups")
    if not os.path.exists(backup_location):
        os.makedirs(backup_location)
    for x in glob.glob(os.path.join(backup_location, "*/*.tar.gz")):
        path = x
        name = os.path.basename(x).split("-")[0]
        meta = x.split(".tar.gz")[0]+".meta"
        stime = x.split("-")[1].split(".tar.gz")[0]
        if not os.path.exists(meta):
            backups.append({"id": name+"/"+stime, "pid": name, "path": path,
                "icon": None, "type": "Unknown", "time": systemtime.get_iso_time(stime),
                "version": "Unknown", "size": os.path.getsize(path),
                "site_type": None, "is_ready": True})
            continue
        with open(meta, "r") as f:
            data = json.loads(f.read())
            backups.append({"id": name+"/"+stime, "pid": name, "path": path,
                "icon": data["icon"], "type": data["type"], "time": data["time"],
                "version": data["version"], "size": os.path.getsize(path),
                "site_type": data.get("site_type", None), "is_ready": True})
    return backups

def get_able():
    able = []
    for x in applications.get(installed=True):
        if x.type != "website" and hasattr(x, "_backup"):
            able.append({"type": "app", "icon": x.icon, "id": x.id})
    for x in websites.get():
        if not isinstance(x, websites.ReverseProxy):
            able.append({"type": "site", "icon": x.meta.icon, "id": x.id})
    for x in get():
        if not x["pid"] in [y["id"] for y in able]:
            able.append({"type": x["type"], "icon": x["icon"], "id": x["pid"]})
    if not "arkOS" in [x["id"] for x in able]:
        able.append({"type": "app", "icon": "fa fa-cog", "id": "arkOS"})
    return able

def create(id, data=True):
    controller = None
    if id == "arkOS":
        controller = arkOSBackupCfg(id="arkOS", icon="fa fa-cog", version=arkos_version)
        return controller.backup()
    app = applications.get(id)
    if app and app.type != "website" and hasattr(app, "_backup"):
        controller = app._backup(app.id, app.icon, version=app.version)
    else:
        sites = websites.get()
        for x in sites:
            if x.id == id:
                controller = x.backup
                break
    if not controller:
        raise Exception("No backup controller found")
    return controller.backup(data=data)

def restore(backup, data=True):
    controller = None
    if backup["type"] == "site":
        sites = websites.get()
        for x in sites:
            if x.id == backup["pid"]:
                controller = x.backup
                break
        else:
            app = applications.get(backup["site_type"])
            controller = app._backup(backup["pid"], backup["icon"], True)
    else:
        app = applications.get(backup["pid"])
        controller = app._backup()
    if not controller:
        raise Exception("No backup controller found")
    b = controller.restore(backup)
    return b

def remove(id, time, backup_location=""):
    if not backup_location:
        backup_location = config.get("backups", "location", "/var/lib/arkos/backups")
    backups = get()
    for x in backups:
        if x["id"] == id+"/"+time:
            os.unlink(x["path"])
            try:
                os.unlink(x["path"].split(".")[1]+".meta")
            except:
                pass

def site_load(site):
    if site.__class__.__name__ != "ReverseProxy":
        controller = site.meta.get_module("backup") or BackupController
        site.backup = controller(site.id, site.meta.icon, site, site.meta.version)
    else:
        site.backup = None

signals.add("backup", "websites", "site_loaded", site_load)
signals.add("backup", "websites", "site_installed", site_load)
