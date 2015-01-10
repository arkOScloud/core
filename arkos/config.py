import json

from arkos.utilities import can_be_int


class Config:
    def __init__(self):
        self.config = {}
    
    def load(self, path):
        self.filename = path
        with open(path) as f:
            self.config = json.loads(f.read())

    def save(self):
        with open(self.filename, 'w') as f:
            f.write(json.dumps(self.config, sort_keys=True, 
                indent=4, separators=(',', ': ')))

    def get(self, section, key, default=None):
        if self.config.has_key(section):
            value = self.config.get(section).get(key) or default
        else:
            value = None or default
        return value

    def set(self, section, key, value):
        if self.config.has_key(section):
            self.config[section][key] = value
        else:
            self.config[section] = {}
            self.config[section][key] = value

    def has_option(self, section, key):
        if self.config.has_key(section):
            return self.config[section].has_key(key)
        else:
            return False
