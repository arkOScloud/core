import os
import shutil
import StringIO
import tarfile

from arkos import config, applications, websites
from arkos.system import systemtime
from arkos.utilities import random_string


class BackupController:
    def __init__(self, id, site=None):
        self.id = id
        self.ctype = "site" if site else "app"
        self.site = site
    
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
            data.append("/etc/nginx/sites-available/%s" % self.site.name)
            data.append(os.path.join(config.get("websites", "site_dir"), self.site.name))
        else:
            data += self.get_data()
        return data
    
    def backup(self, data=True, backup_location="/var/lib/arkos/backups"):
        if self.ctype == "site":
            self.pre_backup(self.site)
        else:
            self.pre_backup()
        
        backup_dir = os.path.join(backup_location, self.id)
        try:
            os.makedirs(backup_dir)
        except:
            pass
        
        config = self._get_config()
        data = self._get_data() if data else []
        timestamp = systemtime.get_serial_time()
        with tarfile.open(os.path.join(backup_dir, '%s-%s.tar.gz' % (self.id,timestamp)), 'w:gz') as t:
            for f in config+data:
                for x in glob.glob(f):
                    t.add(x)
            meta = StringIO.StringIO(self.id)
            minfo = tarfile.TarInfo(name="/arkos-backup")
            minfo.size = len(meta.buf)
            t.addfile(tarinfo=minfo, fileobj=meta)
            if self.ctype == "site" and self.site.db:
                dbsql = StringIO.StringIO(self.db.dump())
                dinfo = tarfile.TarInfo(name="/%s.sql"%self.site.name)
                dinfo.size = len(dbsql.buf)
                t.addfile(tarinfo=dinfo, fileobj=dbsql)

        if self.ctype == "site":
            self.post_backup(self.site)
        else:
            self.post_backup()
    
    def restore(self, path):
        from arkos import websites, databases
        self.pre_restore()
        
        sitename = ""
        with tarfile.open(path, 'r:gz') as t:
            for f in t.getnames():
                for x in glob.glob(f):
                    if os.path.isdir(x):
                        shutil.rmtree(x)
                    else:
                        if x.startswith("/etc/nginx/sites-available"):
                            sitename = os.path.basename(x)
                        os.unlink(x)
            t.extractall("/")
        os.unlink("/arkos-backup")
        
        dbpasswd = ""
        if self.ctype == "site" and sitename and not websites.get(sitename):
            websites.scan()
            self.site = websites.get(sitename)
            g = ConfigParser.SafeConfigParser()
            g.read(os.path.join(self.path, ".arkos"))
            if g.get('website', 'dbengine', None) and os.path.exists("/%s.sql"%sitename):
                dbname = g.get("website", "dbname")
                dbmgr = databases.get(g.get("website", "dbengine"))
                dbmgr = databases.get_managers(dbmgr)
                if databases.get(dbname):
                    databases.get(dbname).remove()
                db = dbmgr.add_db(dbname)
                with open("/%s.sql"%sitename, "r") as f:
                    db.execute(f.read())
                os.unlink("/%s.sql"%sitename)
                if dbmgr.meta.database_multiuser:
                    passwd = random_string()[0:16]
                    if databases.get_users(sitename):
                        databases.get_users(sitename).remove()
                    u = dbmgr.add_user(sitename, passwd)
                    u.chperm("allow", db)
        
        if self.ctype == "site":
            self.post_restore(self.site, dbpasswd)
            self.site.enable()
        else:
            self.post_restore()
    
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


def get(backup_location="/var/lib/arkos/backups"):
    backups = {}
    for x in os.listdir(backup_location):
        backups[x] = []
        archives = os.listdir(os.path.join(backup_location, x))
        archives = sorted(archives, key=lambda y: int(y.split("-")[1].split(".tar.gz")[0]))
        for y in archives:
            if not y.endswith(".tar.gz"):
                continue
            time = y.split("-")[1].split(".tar.gz")[0]
            path = os.path.join(backup_location, x, y)
            backups[x][time] = {"id": x, "time": time, "path": path, 
                "size": os.path.getsize(path)}
    return backups

def get_able():
    able = []
    for x in applications.get():
        if app.type != "website" and hasattr(x, "_backup"):
            able.append({"type": "app", "id": x.id})
    for x in websites.get():
        able.append({"type": "site", "id": x.name})
    return able

def create(name, data=True):
    controller = None
    app = applications.get(name)
    if app and app.type != "website" and hasattr(app, "_backup"):
        controller = app._backup()
    else:
        sites = websites.get()
        for x in sites:
            if x.name == name:
                controller = x.backup
                break
    if not controller:
        raise Exception("No backup controller found")
    controller.backup(data=data)

def restore(backup, data=True):
    controller = None
    app = applications.get(backup["id"])
    if app and app.type != "website" and hasattr(app, "_backup"):
        controller = app._backup()
    else:
        sites = websites.get()
        for x in sites:
            if x.name == backup["id"]:
                controller = x.backup
                break
    if not controller:
        raise Exception("No backup controller found")
    controller.restore(backup["path"])

def remove(id, time, backup_location="/var/lib/arkos/backups"):
    backups = get()
    if id in backups and time in backups[id]:
        os.unlink(backups[id][time]["path"])
