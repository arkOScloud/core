import os

from arkos.core.utilities import shell


def verify_path(self):
    profile = []
    with open('/etc/profile', 'r') as f:
        for l in f.readlines():
            if l.startswith('PATH="') and not '/usr/lib/ruby/gems/2.0.0/bin' in l:
                l = l.split('"\n')[0]
                l += ':/usr/lib/ruby/gems/2.0.0/bin"\n'
                profile.append(l)
                os.environ['PATH'] = os.environ['PATH'] + ':/usr/lib/ruby/gems/2.0.0/bin'
            else:
                profile.append(l)
    with open('/etc/profile', 'w') as f:
        f.writelines(profile)

def install_gem(self, *gems, **kwargs):
    self.verify_path()
    gemlist = shell('gem list')["stdout"].split('\n')
    for x in gems:
        if not any(x==s for s in gemlist) or force:
            d = shell('gem install -N --no-user-install %s' % x)
            if d["code"] != 0:
                self.app.log.error('Gem install \'%s\' failed: %s'%(x,str(d["stderr"])))
                raise Exception('Gem install \'%s\' failed. See logs for more info'%x)
