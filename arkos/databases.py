import imp

from arkos import storage


class Database:
    def __init__(self, name="", user=None):
        self.name = name
        self.user = user
    
    def add(self):
        pass
    
    def remove(self):
        pass
    
    def chperm(self):
        pass
    
    def execute(self):
        pass


class DatabaseUser:
    def __init__(self, name=""):
        self.name = name
    
    def chperm(self):
    
    def remove(self):
        pass


class DatabaseManager:
    def __init__(self, id="", name="", conn=None):
        self.id = id
        self.name = name
        self.conn = conn
    
    def connect(self):
        pass

    def get_dbs(self):
        pass
    
    def get_users(self):
        pass
    

def get():
    dbs = []
    managers = storage.dbs.get("managers")
    if not managers:
        managers = get_managers()
        storage.dbs.set("managers", managers)
    for x in managers:
        dbs += x.get_dbs()
    return dbs

def get_users():
    users = []
    managers = storage.dbs.get("managers")
    if not managers:
        managers = get_managers()
        storage.dbs.set("managers", managers)
    for x in managers:
        users += x.get_users()
    return users

def get_managers():
    mgrs = []
    for x in storage.apps.get():
        if x.atype == "database":
            dbm = imp.load_module(x["id"]+".dbengine."+x["name"], *imp.find_module(x["id"], [config.get("apps", "app_dir")]))
            mgrs.append(dbm())
    return mgrs

def get_types():
    types = []
    managers = storage.dbs.get("managers")
    if not managers:
        managers = get_managers()
        storage.dbs.set("managers", managers)
    return [x.name for x in managers]
