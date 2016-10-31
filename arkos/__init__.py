"""
Initializer functions for arkOS.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import os

from arkos import configs
from arkos.utilities import test_dns
from arkos.utilities.logs import LoggingControl
from arkos.connections import ConnectionsManager
from arkos.utilities import detect_architecture

version = "0.8.2"


class StorageControl:
    """The primary controller for all Storage classes."""
    TYPES = [
        "applications", "websites", "certificates", "certificate_authorities",
        "databases", "database_users", "database_engines", "updates",
        "policies", "shared_files", "shares", "mounts", "share_engines",
        "signals"
    ]

    def __init__(self):
        """Initialize arkOS storage."""
        for x in self.TYPES:
            setattr(self, x, {})


def init(
        config_path="", secrets_path="", policies_path="", debug=False,
        test=False, log=None):
    """
    Initialize and load arkOS config data.

    If ``config_path`` or ``policies_path`` are not supplied, default values
    will be used.

    :param str config_path: Path to config file on disk.
    :param str secrets_path: Path to secrets file on disk.
    :param str policies_path: Path to policies file on disk.
    :param bool debug: Set log level to DEBUG
    :param bool test: Use default configurations for testing if no config_path
    :param logger log: Use this logger instead of creating a new one
    """
    if test:
        debug = True
        config_path = config_path or "/etc/arkos/settings-test.json"
    else:
        config_path = config_path or "/etc/arkos/settings.json"
    policies_path = policies_path or "/etc/arkos/policies.json"
    secrets_path = secrets_path or "/etc/arkos/secrets.json"
    config.load(
        config_path,
        default=configs.DEFAULT_CONFIG if not test else configs.TEST_CONFIG
    )
    secrets.load(secrets_path, default={})
    policies.load(policies_path, default={})

    if log:
        logger.logger = log
    logger.add_stream_logger(
        debug=debug or config.get("general", "debug", False)
    )
    if not os.path.exists(config_path):
        logger.warning("Init", "Config not found. Using defaults...")

    arch = detect_architecture()
    config.set("enviro", "version", version)
    config.set("enviro", "arch", arch[0])
    config.set("enviro", "board", arch[1])
    if not test_dns("arkos.io"):
        logger.warning("Init", "DNS resolution failed. Please make sure your "
                       "server network connection is properly configured.")
    conns.connect()
    return config


def initial_scans():
    """Setup initial scans for all arkOS objects."""
    from arkos import applications, backup, certificates, databases, websites
    from arkos import tracked_services
    applications.scan(cry=False)
    backup.get()
    certificates.scan()
    databases.scan()
    websites.scan()
    tracked_services.initialize()
    if config.get("general", "enable_upnp"):
        tracked_services.initialize_upnp(tracked_services.get())


config = configs.Config("settings.json")
secrets = configs.Config("secrets.json")
policies = configs.Config("policies.json")
storage = StorageControl()
conns = ConnectionsManager(config, secrets)
logger = LoggingControl()
