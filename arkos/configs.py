"""
Classes and functions for management of arkOS configuration files.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import copy
import json
import os

import arkos
from arkos.utilities.errors import ConfigurationError

DEFAULT_CONFIG = {
    "general": {
        "repo_server": "grm.arkos.io",
        "policy_path": "/etc/arkos/policies.json",
        "firewall": True,
        "enable_upnp": True,
        "ntp_server": "ntp.arkos.io",
        "date_format": "DD MMM YYYY",
        "time_format": "HH:mm:ss",
        "ldap_uri": "ldap://localhost",
        "ldap_rootdn": "dc=arkos-servers,dc=org",
        "ldap_conntype": "dynamic"
    },
    "apps": {
        "app_dir": "/var/lib/arkos/applications",
        "purge": True
    },
    "certificates": {
        "cert_dir": "/etc/arkos/ssl/certs",
        "key_dir": "/etc/arkos/ssl/keys",
        "ca_cert_dir": "/etc/arkos/ssl/ca_certs",
        "ca_key_dir": "/etc/arkos/ssl/ca_keys",
        "acme_dir": "/etc/arkos/ssl/acme/certs",
        "acme_server": "https://acme-v01.api.letsencrypt.org/directory",
        "ciphers": "ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384:kEDH+AESGCM:ECDHE-RSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA:ECDHE-ECDSA-AES256-SHA:DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA:DHE-RSA-AES256-SHA256:DHE-DSS-AES256-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:ECDHE-RSA-DES-CBC3-SHA:ECDHE-ECDSA-DES-CBC3-SHA:EDH-RSA-DES-CBC3-SHA:EDH-DSS-DES-CBC3-SHA:DES-CBC3-SHA:HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK"
    },
    "websites": {
        "site_dir": "/srv/http/webapps"
    },
    "filesystems": {
        "vdisk_dir": "/vdisk",
        "cipher": "aes-xts-plain64",
        "keysize": 256
    },
    "updates": {
        "check_updates": True,
        "current_update": 0
    },
    "backups": {
        "driver": "filesystem",
        "location": "/var/lib/arkos/backups"
    },
    "genesis": {
        "anonymous": True,
        "host": "0.0.0.0",
        "port": 8000,
        "ssl": False,
        "cert_file": "",
        "key_file": "",
        "firstrun": False
    }
}

TEST_CONFIG = copy.deepcopy(DEFAULT_CONFIG)
TEST_CONFIG["general"].update({
    "repo_server": "grm-test.arkos.io",
    "enable_upnp": False,
    "ldap_conntype": "simple"
})
TEST_CONFIG["certificates"].update({
    "acme_server": "https://acme-staging.api.letsencrypt.org/directory"
})
TEST_CONFIG["genesis"].update({"firstrun": True})


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
        self.default = {}
        self.filename = filename

    def load(self, path, default=None):
        """
        Load the config from file.

        If ``default`` is specified, that object will be used as a config
        if the ``path`` does not exist. If it is not specified, an Exception
        will be thrown in this circumstance.

        :param str path: Path to config file on disk.
        :param dict default: Default configuration to use
        """
        self.default = default
        if os.path.exists(path):
            with open(path, "r") as f:
                self.config = json.loads(f.read())
            self.path = path
        else:
            if default is None:
                raise ConfigurationError("{0} not found".format(self.filename))
            else:
                self.load_object(self.default, path)
                self.path = path

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
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))
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
            value = self.config.get(section, default)
        elif section in self.config:
            value = self.config.get(section).get(key, default)
            if value is None and self.default and section in self.default:
                value = self.default.get(section).get(key, default)
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
