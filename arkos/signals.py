from arkos import storage
    

class Listener:
    def __init__(self, by, id, sig, func):
        self.id = id
        self.by = by
        self.sig = sig
        self.func = func
    
    def trigger(self, data, crit=True):
        try:
            if data:
                self.func(data)
            else:
                self.func()
        except:
            if crit:
                raise


def add(by, id, sig, func):
    l = Listener(by, id, sig, func)
    storage.signals.add("listeners", l)

def emit(id, sig, data=None, crit=True):
    s = storage.signals.get("listeners")
    for x in s:
        if x.id == id and x.sig == sig:
            x.trigger(data, crit)

def remove(by):
    sigs = storage.signals.get("listeners")
    for x in sigs:
        if x.by == by:
            storage.signals.remove("listeners", by)
