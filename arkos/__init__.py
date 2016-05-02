import json
import os
import sys

from arkos.config import Config
from arkos.storage import StorageControl
from arkos.utilities.errors import ConfigurationError
from arkos.utilities.logs import LoggingControl, new_logger
from arkos.connections import ConnectionsManager

version = "0.7.2"

config = Config("settings.json")
secrets = Config("secrets.json")
policies = Config("policies.json")
storage = StorageControl()
conns = ConnectionsManager()
logger = LoggingControl()

def init(config_path="/etc/arkos/settings.json", secrets_path="/etc/arkos/secrets.json",
        policies_path="/etc/arkos/policies.json", log=None):
    config.load(config_path)
    secrets.load(secrets_path)
    policies.load(policies_path)
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
