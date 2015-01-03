from arkos.core.frameworks import Framework
from arkos.core.utilities import dictfilter


class Databases(Framework):
    REQUIRES = ["apps", "services", "database_engines"]

    def on_start(self):
        self.get(types=self.get_types())

    def get(self, **kwargs):
        dbs = []
        if self.app.storage:
            dbs = self.app.storage.get_list("databases:databases")
        if not self.app.storage or not dbs:
            dbs = self.scan_databases()
        if self.app.storage:
            self.app.storage.append_all("databases:databases", dbs)
        return dictfilter(dbs, kwargs)

    def get_users(self, **kwargs):
        dbs = []
        if self.app.storage:
            users = self.app.storage.get_list("databases:users")
        if not self.app.storage or not users:
            users = self.scan_users()
        if self.app.storage:
            self.app.storage.append_all("databases:users", users)
        return dictfilter(users, kwargs)

    def get_types(self):
        tlist = []
        for x in self.apps.get(type="database"):
            active = True
            if x["database_engine"]:
                status = self.services.get_status(x["database_engine"])
                active = status == "running"
            dblist.append((x, active))
        return tlist

    def scan_databases(self, types=[]):
        dblist = []
        types = [x for x in (types or self.get_types()) if x[1]]
        for x in types:
            xmod = self.database_engines.get(x[0]["pid"])
            for db in xmod.get_dbs():
                dblist.append(db)
        return dblist

    def scan_users(self, types=[]):
        userlist = []
        types = [x for x in (types or self.get_types()) if x[1]]
        for x in types:
            if x[0]["database_multiuser"]:
                xmod = self.database_engines.get(x[0]["pid"])
                for user in xmod.get_users():
                    userlist.append(user)
        return userlist
