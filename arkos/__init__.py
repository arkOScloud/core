"""
Initializer functions for arkOS.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos.config import Config
from arkos.storage import StorageControl
from arkos.utilities import test_dns
from arkos.utilities.logs import LoggingControl, new_logger
from arkos.connections import ConnectionsManager

version = "0.8.0"

config = Config("settings.json")
secrets = Config("secrets.json")
policies = Config("policies.json")
storage = StorageControl()
conns = ConnectionsManager()
logger = LoggingControl()


def init(config_path="/etc/arkos/settings.json",
         secrets_path="/etc/arkos/secrets.json",
         policies_path="/etc/arkos/policies.json", log=None):
    """Initialize and load arkOS config data."""
    config.load(config_path)
    secrets.load(secrets_path)
    policies.load(policies_path)
    conns.connect(config, secrets)
    if not test_dns("arkos.io"):
        raise Exception("DNS resolution failed. Please make sure your server"
                        " network connection is properly configured.")
    logger.logger = log or new_logger(20, debug=True)
    return config


def initial_scans():
    """Setup initial scans for all arkOS objects."""
    from arkos import applications, certificates, databases, websites
    from arkos import tracked_services
    applications.scan()
    certificates.scan()
    databases.scan()
    websites.scan()
    tracked_services.initialize()
    if config.get("general", "enable_upnp", True):
        tracked_services.initialize_upnp(tracked_services.get())
