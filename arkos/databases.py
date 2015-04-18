from arkos import storage, signals, applications
from arkos.utilities import random_string


class Database:
    def __init__(self, id="", manager=None):
        self.id = id
        self.manager = manager
    
    def add(self):
        signals.emit("databases", "pre_add", self)
        self.add_db()
        storage.dbs.add("databases", self)
        signals.emit("databases", "post_add", self)
    
    def add_db(self):
        pass
    
    def remove(self):
        signals.emit("databases", "pre_remove", self)
        self.remove_db()
        storage.dbs.remove("databases", self)
        signals.emit("databases", "post_remove", self)
    
    def remove_db(self):
        pass
    
    def execute(self):
        pass
    
    def as_dict(self):
        return {
            "id": self.id,
            "type_id": self.manager.id,
            "type_name": self.manager.name,
            "size": self.get_size(),
            "is_ready": True
        }


class DatabaseUser:
    def __init__(self, id="", passwd="", manager=None):
        self.id = id
        self.passwd = passwd
        self.manager = manager
    
    def add(self, passwd):
        signals.emit("databases", "pre_user_add", self)
        self.add_user(passwd)
        storage.dbs.add("users", self)
        signals.emit("databases", "post_user_add", self)
    
    def add_user(self):
        pass
    
    def remove(self):
        signals.emit("databases", "pre_user_remove", self)
        self.remove_user()
        storage.dbs.remove("users", self)
        signals.emit("databases", "post_user_remove", self)
    
    def remove_user(self):
        pass
    
    def chperm(self):
        pass

    def as_dict(self):
        return {
            "id": self.id,
            "type_id": self.manager.id,
            "type_name": self.manager.name,
            "permissions": self.chperm("check"),
            "is_ready": True
        }


class DatabaseManager:
    def __init__(self, id="", name="", meta=None):
        self.id = id
        self.name = name
        self.meta = meta
        self.state = True
        try:
            self.connect()
        except:
            pass
    
    def connect(self):
        pass

    def get_dbs(self):
        return []
    
    def add_db(self, name):
        pass
    
    def get_users(self):
        return []
    
    def add_user(self, name, passwd):
        pass
    
    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "supports_users": self.meta.database_multiuser
        }


def get(id=None, type=None):
    data = scan()
    if id or type:
        tlist = []
        for x in data:
            if x.id == id:
                return x
            elif x.manager.id == type:
                tlist.append(x)
        if tlist:
            return tlist
        return None
    return data

def scan():
    dbs = []
    for x in get_managers():
        try:
            dbs += x.get_dbs()
        except:
            continue
    storage.dbs.set("databases", dbs)
    return dbs

def get_user(id=None, type=None):
    data = scan_users()
    if id or type:
        tlist = []
        for x in data:
            if x.id == id:
                return x
            elif x.manager.id == type:
                tlist.append(x)
        if tlist:
            return tlist
        return None
    return data

def scan_users():
    users = []
    for x in get_managers():
        try:
            users += x.get_users()
        except:
            continue
    storage.dbs.set("users", users)
    return users

def get_managers(id=None):
    data = storage.dbs.get("managers")
    if not data:
        data = scan_managers()
    if id:
        for x in data:
            if x.id == id:
                return x
        return None
    return data

def scan_managers():
    mgrs = []
    for x in applications.get(type="database"):
        if x.installed:
            mgrs.append(x._database_mgr(id=x.id, name=x.name, meta=x))
    storage.dbs.set("managers", mgrs)
    return mgrs
