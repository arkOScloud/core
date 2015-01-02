import json

from arkos.core import Framework


class Config(object):
    def __init__(self, storage=None):
        self.storage = storage
        if not self.storage:
            self.config = {}
    
    def load(self, path):
        self.filename = path
        with open(path) as f:
            config = json.loads(f.read())
        if self.storage:
            for x in config:
                self.storage.set("config:%s" % x, config[x])
        else:
            self.config = config

    def save(self):
        d = {}
        if self.storage:
            for x in self.storage.scan("config:*"):
                section = x.split(":", 2)[2]
                if section.startswith("enviro"):
                    continue
                d[section] = self.storage.get("config:%s" % section)
        else:
            d = self.config
        with open(self.filename, 'w') as f:
            f.write(json.dumps(d, sort_keys=True, 
                indent=4, separators=(',', ': ')))

    def get(self, section, key, default=None):
        if self.storage:
            value = self.storage.get("config:%s" % section, key) or default
            if value in ["True", "False"]:
                value = bool(value)
        elif self.config.has_key(section):
            value = self.config.get(section).get(key) or default
        else:
            value = None or default
        return value

    def set(self, section, key, value):
        if self.storage:
            value = str(value) if type(value) == bool else value
            self.storage.set("config:%s" % section, key, value)
        elif self.config.has_key(section):
            self.config[section][key] = value
        else:
            self.config[section] = {}
            self.config[section][key] = value

    def has_option(self, section, key):
        if self.storage:
            return self.storage.has_option("config:%s" % section, key)
        elif self.config.has_key(section):
            return self.config[section].has_key(key)
        else:
            return False
