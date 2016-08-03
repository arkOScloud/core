"""
Classes and functions for management of arkOS configuration files.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import json
import os

import arkos
from arkos.utilities import can_be_int
from arkos.utilities.errors import ConfigurationError


class Config:
    """
    A class for managing arkOS configuration files.

    This class can be used for managing any type of arkOS JSON-based config
    file, including ``settings.json`` and ``secrets.json``.
    """
    
    def __init__(self, filename):
        """
        Initialize the Config object.

        :param str filename: name of file under base config directory
        """
        self.config = {}
        self.filename = filename

    def load(self, path):
        """
        Load the config from file.

        :param str path: Path to config file on disk.
        """
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
        """Save the config in memory to disk."""
        config = self.config.copy()
        if config.has_key("enviro"):
            del config["enviro"]
        with open(self.path, 'w') as f:
            f.write(json.dumps(self.config, sort_keys=True,
                indent=4, separators=(',', ': ')))

    def get(self, section, key=None, default=None):
        """
        Get a config section or key.

        :param str section: Section name
        :param str key: Key name (optional)
        :param default: Default value to return if not found
        :returns: Config section (dict) or key (str/int/dict/list)
        """
        if self.config.has_key(section) and type(self.config.get(section)) not in [dict, list]:
            return self.config.get(section)
        elif self.config.has_key(section):
            value = self.config.get(section).get(key) or default
        else:
            value = None or default
        return value

    def get_all(self, section=None):
        """
        Get all values in the config, or all values in a section.

        :param str section: Section name (optional)
        :returns: Entire config or config section
        :rtype: dict
        """
        if section:
            return self.config.get(section, {})
        return self.config

    def set(self, section, key, value=None):
        """
        Set a config section or key value.

        :param str section: Section name
        :param key: Key name (str) OR section (dict) to set
        :param str value: If setting key, value to set
        """
        if value == None:
            self.config[section] = key
        elif self.config.has_key(section):
            self.config[section][key] = value
        else:
            self.config[section] = {}
            self.config[section][key] = value

    def append(self, section, key, value=None):
        """
        Append a value to a list-type key.

        :param str section: Section name
        :param str key: Key name
        :param str value: Value to append to list
        """
        if value == None:
            if not self.config.has_key(section):
                self.config[section] = []
            self.config[section].append(key)
        elif self.config.has_key(section):
            self.config[section][key].append(value)
        else:
            self.config[section] = {}
            self.config[section][key] = [value]

    def remove(self, section, key):
        """
        Remove a key from the config.

        :param str section: Section name
        :param str key: Key name
        """
        if self.config.has_key(section) and len(self.config[section]) <= 1:
            del self.config[section]
        elif self.config.has_key(section) and self.config[section].has_key(key):
            del self.config[section][key]

    def has_option(self, section, key):
        """
        State if the config has the specified key present.

        :param str section: Section name
        :param str key: Key name
        :returns: True if option is present
        :rtype: bool
        """
        if self.config.has_key(section):
            return self.config[section].has_key(key)
        else:
            return False
        
    def _set_enviro(self):
        """Private method to set environment variables in the loaded config."""
        arch = detect_architecture()
        self.set("enviro", "version", arkos.version)
        self.set("enviro", "arch", arch[0])
        self.set("enviro", "board", arch[1])
