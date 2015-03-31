from arkos import storage
from arkos.system import systemtime


class Share:
    def __init__(self, id, path, expires=0):
        self.id = id
        self.path = path
        self.expires = expires
        self.fetch_count = 0
    
    def add(self):
        storage.files.add("shares", self)
    
    def delete(self):
        storage.files.remove("shares", self)
    
    def is_expired(self):
        return (self.expires != 0 and self.expires < systemtime.get_unix_time())
    
    def update_expiry(self, nexpiry):
        if nexpiry == False:
            self.expires = 0
        else:
            self.expires = systemtime.get_unix_time(nexpiry)
    
    def as_dict(self):
        return {
            "id": self.id,
            "path": self.path,
            "expires": self.expires!=0,
            "expires_at": systemtime.get_iso_time(self.expires, "unix") if self.expires != 0 else "",
            "fetch_count": self.fetch_count
        }


def get(id=None):
    data = storage.files.get("shares")
    to_purge = []
    for x in data:
        if x.is_expired():
            to_purge.append(x)
    for x in to_purge:
        x.delete()
    if id:
        for x in data:
            if x.id == id:
                return x
        return None
    return data
