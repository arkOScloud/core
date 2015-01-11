import os
import sys

from arkos.connections import *
from arkos.config import Config
from arkos.storage import Storage
from arkos.utilities import new_logger


class StorageControl:
    def __init__(self):
        self.apps = Storage(["installed", "available", "updatable"])
        self.sites = Storage(["sites"])
        self.certs = Storage(["certificates", "authorities"])
        self.dbs = Storage(["databases", "users", "managers"])
        self.points = Storage(["points"])
        self.updates = Storage(["updates"])


class ConnectionsManager:
    def __init__(self):
        self.LDAP = ldap_connect(config=config)
        self.SystemD = systemd_connect()
        self.Supervisor = supervisor_connect()


config = Config()
if os.path.exists(os.path.join(sys.path[0], "settings.json")):
    config.load(os.path.join(sys.path[0], "settings.json"))
elif os.path.exists("/etc/arkos/settings.json"):
    config.load("/etc/arkos/settings.json")
storage = StorageControl()
logger = new_logger(20, debug=False)
conns = ConnectionsManager()
