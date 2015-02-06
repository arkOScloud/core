from arkos import storage, applications
from arkos.utilities import random_string


class Database:
    def __init__(self, id="", name="", manager=None):
        self.id = id or random_string()[0:8]
        self.name = name
        self.manager = manager
    
    def add(self):
        self.add_db()
        storage.dbs.add("databases", self)
    
    def add_db(self):
        pass
    
    def remove(self):
        self.remove_db()
        storage.dbs.remove("databases", self)
    
    def remove_db(self):
        pass
    
    def execute(self):
        pass
    
    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type_id": self.manager.id,
            "type_name": self.manager.name,
            "size": self.get_size(),
            "is_ready": True
        }


class DatabaseUser:
    def __init__(self, id="", name="", passwd="", manager=None):
        self.id = id or random_string()[0:8]
        self.name = name
        self.passwd = passwd
        self.manager = manager
    
    def add(self, passwd):
        self.add_user(passwd)
        storage.dbs.add("users", self)
    
    def add_user(self):
        pass
    
    def remove(self):
        self.remove_user()
        storage.dbs.remove("users", self)
    
    def remove_user(self):
        pass
    
    def chperm(self):
        pass

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
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
            self.state = False
    
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
    data = storage.dbs.get("databases")
    if not data:
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
        if x.state:
            dbs += x.get_dbs()
    storage.dbs.set("databases", dbs)
    return dbs

def get_user(id=None, type=None):
    data = storage.dbs.get("users")
    if not data:
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
        if x.state:
            users += x.get_users()
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
        mgrs.append(x._database_mgr(id=x.id, name=x.name, meta=x))
    storage.dbs.set("managers", mgrs)
    return mgrs
