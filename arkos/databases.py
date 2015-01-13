from arkos import storage


class Database:
    def __init__(self, name="", manager=None):
        self.name = name
        self.manager = manager
    
    def add(self):
        pass
    
    def remove(self):
        pass
    
    def execute(self):
        pass


class DatabaseUser:
    def __init__(self, name="", passwd=""):
        self.name = name
        self.passwd = passwd
    
    def add(self):
        pass
    
    def chperm(self):
        pass
    
    def remove(self):
        pass


class DatabaseManager:
    def __init__(self, id="", name=""):
        self.id = id
        self.name = name
        self.connect()
    
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
    for x in storage.apps.get("installed"):
        if x.type == "database":
            mgrs.append(x._database_manager())
    return mgrs

def get_types():
    types = []
    managers = storage.dbs.get("managers")
    if not managers:
        managers = get_managers()
        storage.dbs.set("managers", managers)
    return [x.name for x in managers]
