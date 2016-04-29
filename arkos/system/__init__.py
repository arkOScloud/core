"""
Initializer for system module.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from . import network
from . import services
from . import stats
from . import systemtime
from . import domains
from . import users
from . import groups
from . import filesystems


__all__ = [
    "network",
    "services",
    "stats",
    "systemtime",
    "domains",
    "users",
    "groups",
    "filesystems"
]
