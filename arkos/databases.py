from arkos import storage, applications


class Database:
    def __init__(self, id=0, name="", manager=None):
        self.id = id or get_new_db_id()
        self.name = name
        self.manager = manager
    
    def add(self):
        pass
    
    def remove(self):
        pass
    
    def execute(self):
        pass
    
    def as_dict(self):
        return {
            "name": self.name,
            "type": self.manager.id,
            "size": self.get_size()
        }


class DatabaseUser:
    def __init__(self, id=0, name="", passwd="", manager=None):
        self.id = id or get_new_dbuser_id()
        self.name = name
        self.passwd = passwd
        self.manager = manager
    
    def add(self):
        pass
    
    def chperm(self):
        pass
    
    def remove(self):
        pass

    def as_dict(self):
        return {
            "name": self.name,
            "type": self.manager.id,
            "permissions": self.chperm("check")
        }


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
        dbs += x.get_dbs()
    storage.dbs.set("databases", dbs)
    return dbs

def get_user(name=None, type=None):
    data = storage.dbs.get("users")
    if not data:
        data = scan_users()
    if name or type:
        tlist = []
        for x in data:
            if x.name == name:
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
        mgrs.append(x._database_manager())
    storage.dbs.set("managers", mgrs)
    return mgrs

def get_types():
    return [x.name for x in get_managers()]

def get_new_db_id():
    return max([x.id for x in get()]) + 1

def get_new_dbuser_id():
    return max([x.id for x in get_users()]) + 1
