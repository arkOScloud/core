"""
Initializer functions for arkOS unit testing.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import json
import os

from arkos import config, secrets, policies, version
from arkos.utilities import test_dns
from arkos.utilities import detect_architecture


def init_testing(log=None):
    """Initialize arkOS library in unit testing mode."""
    defaults = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "defaults")
    with open(os.path.join(defaults, "settings.json"), "r") as f:
        defsets = json.loads(f.read())
    defsets["general"].update({"ldap_conntype": "simple"})
    config.load_object(defsets)
    secrets.load_object({"ldap": "admin"})
    policies.load_object({})
    # Manually trigger Connections at appropriate place in testing
    arch = detect_architecture()
    config.set("enviro", "version", version)
    config.set("enviro", "arch", arch[0])
    config.set("enviro", "board", arch[1])
    if not test_dns("arkos.io"):
        raise Exception("DNS resolution failed. Please make sure your server"
                        " network connection is properly configured.")
    return (config, secrets, policies)
