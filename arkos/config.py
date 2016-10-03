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
            dir = os.path.dirname(os.path.abspath(
                os.path.dirname(arkos.__file__)))
            if os.path.exists(os.path.join(dir, self.filename)):
                path = os.path.join(dir, self.filename)
            else:
                raise ConfigurationError("{0} not found".format(self.filename))
        self.path = path
        with open(path) as f:
            self.config = json.loads(f.read())

    def load_object(self, obj, path=""):
        """
        Load the config from a dictionary object.

        If `path` is empty, config will not be saved.

        :param dict obj: dictionary to load as config
        :param str path: Path to save to on disk
        """
        self.config = obj
        self.path = path

    def save(self):
        """Save the config in memory to disk."""
        if not self.path:
            return
        config = self.config.copy()
        if "enviro" in config:
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
        if section in self.config \
                and type(self.config.get(section)) not in [dict, list]:
            return self.config.get(section)
        elif section in self.config:
            value = self.config.get(section).get(key)
        else:
            value = None or default
        return default if value in [None, [], {}] else value

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
        if value is None:
            self.config[section] = key
        elif section in self.config:
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
        if value is None:
            if section not in self.config:
                self.config[section] = []
            self.config[section].append(key)
        elif section in self.config:
            self.config[section][key].append(value)
        else:
            self.config[section] = {}
            self.config[section][key] = [value]

    def remove_list(self, section, key, value=None):
        """
        Remove and return a value from a list-type key.

        :param str section: Section name
        :param str key: Key name
        :param str value: Value to remove from list
        """
        if value is None:
            if section not in self.config:
                return
            return self.config[section].remove(key)
        elif section in self.config:
            return self.config[section][key].remove(value)
        return

    def remove(self, section, key):
        """
        Remove a key from the config.

        :param str section: Section name
        :param str key: Key name
        """
        if section in self.config and len(self.config[section]) <= 1:
            del self.config[section]
        elif section in self.config and key in self.config[section]:
            del self.config[section][key]

    def has_option(self, section, key):
        """
        State if the config has the specified key present.

        :param str section: Section name
        :param str key: Key name
        :returns: True if option is present
        :rtype: bool
        """
        if section in self.config:
            return key in self.config[section]
        else:
            return False
