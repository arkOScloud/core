"""
Classes and functions for management of arkOS app backups.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import configparser
import glob
import io
import json
import os
import tarfile

from arkos import version as arkos_version
from arkos import logger, secrets, config, signals
from arkos import applications, databases, websites
from arkos.messages import Notification, NotificationThread
from arkos.system import systemtime
from arkos.utilities import errors, random_string, shell


class BackupController:
    """
    Controller for managing an application's backup functions.

    A BackupController is intended to be included by each app through creating
    a ``backup.py`` module bundled in the app package. This module creates a
    class that subclasses this one and provides app-specific code for obtaining
    config and data file paths, as well as hooks for pre- and post-backup and
    restore actions.

    See ``backup.get()`` for definition of ``Backup`` dict.
    """

    def __init__(self, id, icon, site=None, version=None):
        """
        Initialize the BackupController.

        :param str id: Application or website ID
        :param str icon: FontAwesome icon ID
        :param Website site: Website object for this controller (if any)
        :param str version: Version of the app/website at the time of backup
        """
        self.id = id
        self.icon = icon
        self.ctype = "site" if site else "app"
        self.site = site
        self.version = version

    def _get_config(self):
        """Private method to obtain an app configuration file list."""
        configs = []
        # If the app is a website, pass its Website object to the controller
        if self.ctype == "site":
            configs += self.get_config(self.site)
        else:
            configs += self.get_config()
        return configs

    def _get_data(self):
        """Private method to obtain an app data file list."""
        data = []
        if self.ctype == "site":
            data += self.get_data(self.site)
            data.append("/etc/nginx/sites-available/{0}".format(self.site.id))
            data.append(self.site.path)
        else:
            data += self.get_data()
        return data

    def backup(self, data=True, backup_location="",
               nthread=NotificationThread()):
        """
        Initiate a backup of the associated arkOS app.

        :param bool data: Include specified data files in the backup?
        :param str backup_location: Save output archive to custom path
        :param NotificationThread nthread: notification thread to use
        :returns: ``Backup``
        :rtype: dict
        """
        nthread.title = "Creating a backup"

        if not backup_location:
            backup_location = config.get("backups", "location",
                                         "/var/lib/arkos/backups")
        if self.ctype == "site":
            self.version = self.site.app.version
        signals.emit("backups", "pre_backup", self)

        msg = "Running pre-backup for {0}...".format(self.id)
        nthread.update(Notification("info", "Backup", msg))
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
        archive_name = "{0}-{1}.tar.gz".format(self.id, timestamp)
        path = os.path.join(backup_dir, archive_name)
        # Zip up the gathered file paths
        nthread.complete(Notification("info", "Backup", "Creating archive..."))
        with tarfile.open(path, "w:gz") as t:
            for f in myconfig+data:
                for x in glob.glob(f):
                    t.add(x)
            if self.ctype == "site" and self.site.db:
                dbsql = io.StringIO(self.site.db.dump())
                dinfo = tarfile.TarInfo(name="/{0}.sql".format(self.site.id))
                dinfo.size = len(dbsql.buf)
                t.addfile(tarinfo=dinfo, fileobj=dbsql)
        # Create a metadata file to track information
        info = {"pid": self.id, "type": self.ctype, "icon": self.icon,
                "version": self.version, "time": isotime}
        if self.site:
            info["site_type"] = self.site.app.id
        filename = "{0}-{1}.meta".format(self.id, timestamp)
        with open(os.path.join(backup_dir, filename), "w") as f:
            f.write(json.dumps(info))

        # Trigger post-backup hook for the app/site
        msg = "Running post-backup for {0}...".format(self.id)
        nthread.update(Notification("info", "Backup", msg))
        if self.ctype == "site":
            self.post_backup(self.site)
        else:
            self.post_backup()
        signals.emit("backups", "post_backup", self)

        msg = "{0} backed up successfully.".format(self.id)
        nthread.complete(Notification("info", "Backup", msg))
        return {"id": "{0}/{1}".format(self.id, timestamp), "pid": self.id,
                "path": path, "icon": self.icon, "type": self.ctype,
                "time": isotime, "version": self.version,
                "size": os.path.getsize(path), "is_ready": True,
                "site_type": self.site.app.id if self.site else None}

    def restore(self, data, nthread=NotificationThread()):
        """
        Restore an associated arkOS app backup.

        :param Backup data: backup to restore
        :param NotificationThread nthread: notification thread to use
        :returns: ``Backup``
        :rtype: dict
        """
        nthread.title = "Restoring backup"

        # Trigger pre-restore hook for the app/site
        signals.emit("backups", "pre_restore", self)
        msg = "Running pre-restore for {0}...".format(data["pid"])
        nthread.update(Notification("info", "Backup", msg))
        self.pre_restore()

        # Extract all files in archive
        sitename = ""
        nthread.update(Notification("info", "Backup", "Extracting files..."))
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
            meta = configparser.SafeConfigParser()
            meta.read(os.path.join(self.site.path, ".arkos"))
            sql_path = "/{0}.sql".format(sitename)
            if meta.get("website", "dbengine", None) \
                    and os.path.exists(sql_path):
                nthread.update(
                    Notification("info", "Backup", "Restoring database..."))
                dbmgr = databases.get_managers(meta.get("website", "dbengine"))
                if databases.get(sitename):
                    databases.get(sitename).remove()
                db = dbmgr.add_db(sitename)
                with open(sql_path, "r") as f:
                    db.execute(f.read())
                os.unlink(sql_path)
                if dbmgr.meta.database_multiuser:
                    dbpasswd = random_string(16)
                    dbuser = databases.get_users(sitename)
                    if dbuser:
                        dbuser.remove()
                    db_user = dbmgr.add_user(sitename, dbpasswd)
                    db_user.chperm("grant", db)

        # Trigger post-restore hook for the app/site
        msg = "Running post-restore for {0}...".format(data["pid"])
        nthread.update(Notification("info", "Backup", msg))
        if self.ctype == "site":
            self.post_restore(self.site, dbpasswd)
            self.site.nginx_enable()
        else:
            self.post_restore()
        signals.emit("backups", "post_restore", self)
        data["is_ready"] = True
        msg = "{0} restored successfully.".format(data["pid"])
        nthread.complete(Notification("info", "Backup", msg))
        return data

    def get_config(self):
        """
        Return configuration file paths to include in backups.

        Apps that subclass this object must override this.

        :returns: Configuration file paths
        :rtype: list
        """
        return []

    def get_data(self):
        """
        Return data file paths to include in backups.

        Apps that subclass this object must override this.

        :returns: Data file paths
        :rtype: list
        """
        return []

    def pre_backup(self):
        """Hook executed before backup. Override in backup module code."""
        pass

    def post_backup(self):
        """Hook executed after backup. Override in backup module code."""
        pass

    def pre_restore(self):
        """Hook executed before restore. Override in backup module code."""
        pass

    def post_restore(self):
        """Hook executed after restore. Override in backup module code."""
        pass


class arkOSBackupCfg(BackupController):
    """BackupController implementation for arkOS core configuration."""

    def get_config(self):
        """Reimplement."""
        return ["/etc/arkos", "/tmp/ldap.ldif"]

    def get_data(self):
        """Reimplement."""
        return []

    def pre_backup(self):
        """Reimplement."""
        s = shell("slapcat -n 1")
        if s["code"] != 0:
            emsg = ("Could not backup LDAP database. "
                    "Please check logs for errors.")
            logger.error("Backup", s["stderr"].decode())
            raise errors.OperationFailedError(emsg)
        with open("/tmp/ldap.ldif", "wb") as f:
            f.write(s["stdout"])

    def post_backup(self):
        """Reimplement."""
        if os.path.exists("/tmp/ldap.ldif"):
            os.unlink("/tmp/ldap.ldif")

    def post_restore(self):
        """Reimplement."""
        if not os.path.exists("/tmp/ldap.ldif"):
            emsg = ("Could not backup LDAP database. "
                    "Please check logs for errors.")
            logger.error("Backup", "/tmp/ldap.ldif not found")
            raise errors.OperationFailedError(emsg)
        with open("/tmp/ldap.ldif", "r") as f:
            ldif = f.read()
        s = shell('ldapadd -D "cn=admin,dc=arkos-servers,dc=org" -w {0}'
                  .format(secrets.get("ldap")),
                  stdin=ldif)
        if os.path.exists("/tmp/ldap.ldif"):
            os.unlink("/tmp/ldap.ldif")
        if s["code"] != 0:
            emsg = ("Could not restore LDAP database. "
                    "Please check logs for errors.")
            logger.error("Backup", s["stderr"].decode())
            raise errors.OperationFailedError(emsg)


def get(backup_location=""):
    """
    Return a list of backup dicts from the backup directory.

    ``Backup`` dicts are in the following format (example):

        {
          "icon": "globe",
          "id": "testghost/20150317124530",
          "is_ready": true,
          "path": "/var/lib/arkos/backups/testghost/testghost-xxx.tar.gz",
          "pid": "testghost",
          "site_type": "ghost",
          "size": 14612219,
          "time": "2015-03-17T12:45:30-04:00",
          "type": "site",
          "version": "0.5.10-1"
        }

    :param str backup_location: Location to scan (instead of arkOS default)
    :returns: backups found
    :rtype: Backup
    """
    backups = []
    if not backup_location:
        backup_location = config.get("backups", "location",
                                     "/var/lib/arkos/backups")
    if not os.path.exists(backup_location):
        os.makedirs(backup_location)
    for x in glob.glob(os.path.join(backup_location, "*/*.tar.gz")):
        path = x
        name = os.path.basename(x).split("-")[0]
        meta = x.split(".tar.gz")[0]+".meta"
        stime = x.split("-")[1].split(".tar.gz")[0]
        if not os.path.exists(meta):
            data = {"id": name+"/"+stime, "pid": name, "path": path,
                    "icon": None, "type": "Unknown",
                    "time": systemtime.get_iso_time(stime),
                    "version": "Unknown", "size": os.path.getsize(path),
                    "site_type": None, "is_ready": True}
            backups.append(data)
            continue
        with open(meta, "r") as f:
            data = json.loads(f.read())
            data = {"id": "{0}/{1}".format(name, stime), "pid": name,
                    "path": path, "icon": data["icon"], "type": data["type"],
                    "time": data["time"], "version": data["version"],
                    "size": os.path.getsize(path), "is_ready": True,
                    "site_type": data.get("site_type", None)}
            backups.append(data)
    return backups


def get_able():
    """
    Obtain a list of arkOS application instances that support backups.

    This list includes all currently installed websites, apps and also arkOS.

    :returns: Website/app information
    :rtype: dict
    """
    able = []
    for x in applications.get(installed=True):
        if x.type != "website" and hasattr(x, "_backup"):
            able.append({"type": "app", "icon": x.icon, "id": x.id})
    for x in websites.get():
        if not isinstance(x, websites.ReverseProxy):
            able.append({"type": "site", "icon": x.app.icon, "id": x.id})
    for x in get():
        if not x["pid"] in [y["id"] for y in able]:
            able.append({"type": x["type"], "icon": x["icon"], "id": x["pid"]})
    if "arkOS" not in [x["id"] for x in able]:
        able.append({"type": "app", "icon": "setting", "id": "arkOS"})
    return able


def create(id, data=True, nthread=NotificationThread()):
    """
    Convenience function to create a backup.

    :param str id: ID of associated app (or website) to backup
    :param bool data: Backup app data also?
    :returns: Backup info
    :rtype: Backup
    """
    controller = None
    if id == "arkOS":
        controller = arkOSBackupCfg("arkOS", "setting",
                                    version=arkos_version)
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
        raise errors.InvalidConfigError("No backup controller found")
    return controller.backup(data=data, nthread=nthread)


def restore(backup, data=True, nthread=NotificationThread()):
    """
    Convenience function to restore a backup.

    :param Backup backup: Backup to restore
    :param bool data: Restore included data files as well?
    :returns: Backup info
    :rtype: Backup
    """
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
        raise errors.InvalidConfigError("No backup controller found")
    b = controller.restore(backup, data, nthread)
    return b


def remove(id, time, backup_location=""):
    """
    Remove a backup.

    :param str id: arkOS app/site ID
    :param str time: Backup timestamp
    :param str backup_location: Location (instead of arkOS default)
    """
    if not backup_location:
        backup_location = config.get("backups", "location",
                                     "/var/lib/arkos/backups")
    backups = get()
    for x in backups:
        if x["id"] == id+"/"+time:
            os.unlink(x["path"])
            try:
                os.unlink(x["path"].split(".")[0]+".meta")
            except:
                pass


def site_load(site):
    """
    Create a BackupController when a Website is first created/loaded.

    :param Website site: Site to create controller for
    """
    if site.__class__.__name__ != "ReverseProxy":
        controller = site.app.get_module("backup") or BackupController
        site.backup = controller(site.id, site.app.icon, site,
                                 site.app.version)
    else:
        site.backup = None

signals.add("backup", "websites", "site_loaded", site_load)
signals.add("backup", "websites", "site_installed", site_load)
