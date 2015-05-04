import json
import os
import sys

from arkos.config import Config, Secrets
from arkos.storage import StorageControl
from arkos.utilities.errors import ConfigurationError
from arkos.utilities.logs import LoggingControl, new_logger
from arkos.connections import ConnectionsManager

version = "0.7.0beta2"

config = Config()
secrets = Secrets()
storage = StorageControl()
conns = ConnectionsManager()
logger = LoggingControl()

def init(config_path="/etc/arkos/settings.json", secrets_path="/etc/arkos/secrets.json",
        log=None):
    config.load(config_path)
    secrets.load(secrets_path)
    conns.connect(config, secrets)
    logger.logger = log or new_logger(20, debug=True)
    return config

def initial_scans():
    from arkos import applications, certificates, databases, websites, tracked_services
    applications.scan()
    certificates.scan()
    databases.scan()
    websites.scan()
    tracked_services.initialize()
