import json
import os
import sys

import arkos
from arkos.utilities import can_be_int
from arkos.utilities.errors import ConfigurationError


class Config:
    def __init__(self, filename):
        self.config = {}
        self.filename = filename

    def load(self, path):
        if not os.path.exists(path):
            dir = os.path.dirname(os.path.abspath(os.path.dirname(arkos.__file__)))
            if os.path.exists(os.path.join(dir, self.filename)):
                path = os.path.join(dir, self.filename)
            else:
                raise ConfigurationError("%s not found" % self.filename)
        self.path = path
        with open(path) as f:
            self.config = json.loads(f.read())

    def save(self):
        config = self.config.copy()
        if config.has_key("enviro"):
            del config["enviro"]
        with open(self.path, 'w') as f:
            f.write(json.dumps(self.config, sort_keys=True,
                indent=4, separators=(',', ': ')))

    def get(self, section, key=None, default=None):
        if self.config.has_key(section) and type(self.config.get(section)) not in [dict, list]:
            return self.config.get(section)
        elif self.config.has_key(section):
            value = self.config.get(section).get(key) or default
        else:
            value = None or default
        return value

    def get_all(self, section=None):
        if section:
            return self.config.get(section, {})
        return self.config

    def set(self, section, key, value=None):
        if value == None:
            self.config[section] = key
        elif self.config.has_key(section):
            self.config[section][key] = value
        else:
            self.config[section] = {}
            self.config[section][key] = value

    def append(self, section, key, value=None):
        if value == None:
            self.config[section].append(key)
        elif self.config.has_key(section):
            self.config[section][key].append(value)
        else:
            self.config[section] = {}
            self.config[section][key] = [value]

    def remove(self, section, key):
        if self.config.has_key(section) and len(self.config[section]) <= 1:
            del self.config[section]
        elif self.config.has_key(section) and self.config[section].has_key(key):
            del self.config[section][key]

    def has_option(self, section, key):
        if self.config.has_key(section):
            return self.config[section].has_key(key)
        else:
            return False
