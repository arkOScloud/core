"""
Initializer functions for arkOS unit testing.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from arkos import config, configs, secrets, policies, version
from arkos.utilities import test_dns
from arkos.utilities import detect_architecture


def init_testing(log=None):
    """Initialize arkOS library in unit testing mode."""
    config.load("", default=configs.TEST_CONFIG)
    secrets.load("", default={"ldap": "admin"})
    policies.load("", default={})
    # Manually trigger Connections at appropriate place in testing
    arch = detect_architecture()
    config.set("enviro", "version", version)
    config.set("enviro", "arch", arch[0])
    config.set("enviro", "board", arch[1])
    if not test_dns("arkos.io"):
        raise Exception("DNS resolution failed. Please make sure your server"
                        " network connection is properly configured.")
    return (config, secrets, policies)
