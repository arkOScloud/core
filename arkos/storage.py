class Storage:
    def __init__(self, types=[]):
        for x in types:
            setattr(self, x, [])
    
    def add(self, stype, item):
        storage = getattr(self, stype)
        storage.append(item)
    
    def set(self, stype, items)
        setattr(self, stype, items)

    def get(self, stype, id=None):
        storage = getattr(self, stype)
        if id:
            for x in storage:
                if id == x.id:
                    return [x]
            return None
        return storage
    
    def get_keyed(self, stype, id=None):
        items = {}
        storage = getattr(self, stype)
        for x in storage:
            items[x.id] = x
        return items
    
    def remove(self, stype, item):
        storage = getattr(self, stype)
        if type(item) == str:
            for x in storage:
                if item == x.id:
                    storage.remove(x)
                    return
        else:
            storage.remove(item)
