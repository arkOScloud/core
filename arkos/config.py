import json
import os
import sys

import arkos
from arkos.utilities import can_be_int
from arkos.utilities.errors import ConfigurationError


class Config:
    def __init__(self):
        self.config = {}

    def load(self, path):
        if not os.path.exists(path):
            dir = os.path.dirname(os.path.abspath(os.path.dirname(arkos.__file__)))
            if os.path.exists(os.path.join(dir, 'settings.json')):
                path = os.path.join(dir, 'settings.json')
            else:
                raise ConfigurationError("Settings file not found")
        self.filename = path
        with open(path) as f:
            self.config = json.loads(f.read())

    def save(self):
        config = self.config.copy()
        if config.has_key("enviro"):
            del config["enviro"]
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


class Secrets:
    def __init__(self):
        self._data = {}

    def load(self, path):
        if not os.path.exists(path):
            dir = os.path.dirname(os.path.abspath(os.path.dirname(arkos.__file__)))
            if os.path.exists(os.path.join(dir, 'secrets.json')):
                path = os.path.join(dir, 'secrets.json')
            else:
                raise ConfigurationError("Secrets file not found")
        self.filename = path
        with open(self.filename, "r") as f:
            self._data = json.loads(f.read())
        for x in self._data:
            setattr(self, x, self._data[x])

    def save(self):
        with open(self.filename, "w") as f:
            f.write(json.dumps(self._data, sort_keys=True,
                indent=4, separators=(",", ": ")))
