"""
Initializer functions for arkOS.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos.configs import Config
from arkos.storages import StorageControl
from arkos.utilities import test_dns
from arkos.utilities.logs import LoggingControl
from arkos.connections import ConnectionsManager
from arkos.utilities import detect_architecture

version = "0.8.0"

config = Config("settings.json")
secrets = Config("secrets.json")
policies = Config("policies.json")
storage = StorageControl()
conns = ConnectionsManager()
logger = LoggingControl()
notify = LoggingControl("notify")


def init(config_path="/etc/arkos/settings.json",
         secrets_path="/etc/arkos/secrets.json",
         policies_path="/etc/arkos/policies.json",
         debug=False, log=None):
    """Initialize and load arkOS config data."""
    config.load(config_path)
    secrets.load(secrets_path)
    policies.load(policies_path)
    conns.connect(config, secrets)
    arch = detect_architecture()
    config.set("enviro", "version", version)
    config.set("enviro", "arch", arch[0])
    config.set("enviro", "board", arch[1])
    if log:
        logger.logger = log
    logger.add_stream_logger(debug or config.get("general", "debug", False))
    if not test_dns("arkos.io"):
        logger.warning("Init", "DNS resolution failed. Please make sure your "
                       "server network connection is properly configured.")
    return config


def initial_scans():
    """Setup initial scans for all arkOS objects."""
    from arkos import applications, certificates, databases, websites
    from arkos import tracked_services
    applications.scan(cry=False)
    certificates.scan()
    databases.scan()
    websites.scan()
    tracked_services.initialize()
    if config.get("general", "enable_upnp", True):
        tracked_services.initialize_upnp(tracked_services.get())
