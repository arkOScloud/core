import subprocess

from config import Config
from storage import Storage
from utilities.logs import new_logger


def version():
    release = '0.7'
    p = subprocess.Popen('git describe --tags 2> /dev/null',
            shell=True,
            stdout=subprocess.PIPE)
    if p.wait() != 0:
        return release
    return p.stdout.read().strip('\n ')

class StorageControl:
    def __init__(self):
        self.apps = Storage(["installed", "available", "updatable"])
        self.sites = Storage(["sites"])
        self.certs = Storage(["certificates", "authorities"])
        self.dbs = Storage(["databases", "users", "managers"])
        self.points = Storage(["points"])
        self.updates = Storage(["updates"])

config = Config()
storage = StorageControl()
logger = new_logger(20, debug=False)
