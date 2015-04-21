import os

from arkos import logger
from arkos.utilities import shell


def verify_path():
    # Verifies that the proper gem dirs are available on the system's exec PATH
    profile = []
    with open("/etc/profile", "r") as f:
        for l in f.readlines():
            if l.startswith("PATH=") and not "/usr/lib/ruby/gems/2.2.0/bin" in l:
                l = l.split('"\n')[0]
                l += ':/usr/lib/ruby/gems/2.2.0/bin"\n'
                profile.append(l)
                os.environ["PATH"] = os.environ["PATH"] + ":/usr/lib/ruby/gems/2.2.0/bin"
            else:
                profile.append(l)
    with open("/etc/profile", "w") as f:
        f.writelines(profile)

def install_gem(*gems, **kwargs):
    # Installs a set of Ruby gems to the system.
    verify_path()
    gemlist = shell("gem list")["stdout"].split("\n")
    for x in gems:
        if not any(x==s for s in gemlist) or force:
            d = shell("gem install -N --no-user-install %s" % x)
            if d["code"] != 0:
                logger.error("Gem install '%s' failed: %s"%(x,str(d["stderr"])))
                raise Exception("Gem install '%s' failed. See logs for more info"%x)

def update_gem(*gems, **kwargs):
    # Updates a set of presently-installed Ruby gems.
    verify_path()
    gemlist = shell("gem list")["stdout"].split("\n")
    for x in gems:
        if not any(x==s for s in gemlist) or force:
            d = shell("gem update -N --no-user-install %s" % x)
            if d["code"] != 0:
                logger.error("Gem update '%s' failed: %s"%(x,str(d["stderr"])))
                raise Exception("Gem update '%s' failed. See logs for more info"%x)
