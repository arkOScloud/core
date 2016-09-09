"""
Helper functions for managing Ruby gems.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import os

from arkos.utilities import errors, shell

BINPATH = "/usr/lib/ruby/gems/2.2.0/bin"


def verify_path():
    """Verify that the proper dirs are available on the system's exec PATH."""
    profile = []
    with open("/etc/profile", "r") as f:
        for l in f.readlines():
            if l.startswith("PATH=") and BINPATH not in l:
                l = l.split('"\n')[0]
                l += ':{0}"\n'.format(BINPATH)
                profile.append(l)
                os.environ["PATH"] = os.environ["PATH"] + ":" + BINPATH
            else:
                profile.append(l)
    with open("/etc/profile", "w") as f:
        f.writelines(profile)


def install_gem(*gems, **kwargs):
    """
    Install a set of Ruby gems to the system.

    If ``force`` is present in kwargs and is True, force reinstall of the gem.

    :param *gems: gems to install
    """
    verify_path()
    gemlist = shell("gem list")["stdout"].split(b"\n")
    for x in gems:
        if not any(x == s for s in gemlist) or kwargs.get('force'):
            d = shell("gem install -N --no-user-install {0}".format(x))
            if d["code"] != 0:
                logmsg = "Gem install of {0} failed.".format(x)
                raise errors.OperationFailedError(logmsg) \
                    from Exception(d["stderr"])


def update_gem(*gems, **kwargs):
    """
    Update a set of presently-installed Ruby gems.

    If ``force`` is present in kwargs and is True, force reinstall of the gem.

    :param *gems: gems to install
    """
    verify_path()
    gemlist = shell("gem list")["stdout"].split("\n")
    for x in gems:
        if not any(x == s for s in gemlist) or kwargs.get('force'):
            d = shell("gem update -N --no-user-install {0}".format(x))
            if d["code"] != 0:
                logmsg = "Gem install of {0} failed.".format(x)
                raise errors.OperationFailedError(logmsg) \
                    from Exception(d["stderr"])
