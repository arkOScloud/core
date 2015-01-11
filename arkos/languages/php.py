import os
import re
import urllib2

from distutils.spawn import find_executable

from arkos.utilities import shell


def install_composer(self):
    cwd = os.getcwd()
    os.chdir("/root")
    os.environ['COMPOSER_HOME'] = '/root'
    self.enable_mod('phar')
    self.open_basedir('add', '/root')
    installer = urllib2.urlopen("https://getcomposer.org/installer").read()
    s = shell('php', stdin=installer)
    os.chdir(cwd)
    if s["code"] != 0:
        raise Exception('Composer download/config failed. Error: %s'%str(s["stderr"]))
    os.rename('/root/composer.phar', '/usr/local/bin/composer')
    os.chmod('/usr/local/bin/composer', 755)
    self.open_basedir('add', '/usr/local/bin')

def verify_composer(self):
    if not find_executable("composer"):
        self.install_composer()
    if not find_executable("composer"):
        raise Exception('Composer was not installed successfully.')

def composer_install(self, path):
    self.verify_composer()
    cwd = os.getcwd()
    os.chdir(path)
    s = shell('composer install')
    os.chdir(cwd)
    if s["code"] != 0:
        raise Exception('Composer failed to install this app\'s bundle. Error: %s'%str(s["stderr"]))

def enable_mod(self, *mod):
    with open('/etc/php/php.ini', 'r') as f:
        lines = f.readlines()
    with open('/etc/php/php.ini', 'w') as f:
        for line in lines:
            for x in mod:
                f.write(re.sub(";extension=%s.so" % mod, "extension=%s.so" % mod, line))

def disable_mod(self, *mod):
    with open('/etc/php/php.ini', 'r') as f:
        lines = f.readlines()
    with open('/etc/php/php.ini', 'w') as f:
        for line in lines:
            for x in mod:
                f.write(re.sub("extension=%s.so" % mod, ";extension=%s.so" % mod, line))

def open_basedir(self, op, path):
    oc = []
    with open('/etc/php/php.ini', 'r') as f:
        ic = f.readlines()
    if op == 'del':
        for l in ic:
            if 'open_basedir = ' in l and path in l:
                l = l.replace(':'+path, '')
                l = l.replace(':'+path+'/', '')
                oc.append(l)
            else:
                oc.append(l)
    else:
        for l in ic:
            if 'open_basedir = ' in l and path not in l:
                l = l.rstrip('\n') + ':%s\n' % path
                oc.append(l)
            else:
                oc.append(l)
    with open('/etc/php/php.ini', 'w') as f:
        f.writelines(oc)

def upload_size(self, size):
    oc = []
    with open('/etc/php/php.ini', 'r') as f:
        ic = f.readlines()
    for l in ic:
        if 'upload_max_filesize = ' in l:
            l = 'upload_max_filesize = %sM' % size
        elif 'post_max_size = ' in l:
            l = 'post_max_size = %sM' % size
        oc.append(l)
    with open('/etc/php/php.ini', 'w') as f:
        f.writelines(oc)
