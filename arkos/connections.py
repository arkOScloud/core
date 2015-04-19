import json
import ldap
import ldap.modlist
import os
import shutil
import sys
import time
import xmlrpclib

from arkos.utilities import shell, random_string, hashpw
from dbus import SystemBus, Interface


class ConnectionsManager:
    def __init__(self, config):
        self.config = config
    
    def connect(self):
        self.DBus = SystemBus()
        self.SystemD = self.SystemDConnect("/org/freedesktop/systemd1", 
            "org.freedesktop.systemd1.Manager")
        self.LDAP = ldap_connect(config=self.config)
        self.Supervisor = supervisor_connect()
    
    def SystemDConnect(self, path, interface):
        systemd = self.DBus.get_object("org.freedesktop.systemd1", path)
        return Interface(systemd, dbus_interface=interface)


def ldap_connect(uri="", rootdn="", dn="cn=admin", config=None, passwd=""):
    if not all([uri, rootdn, dn]) and not config:
        raise Exception("No configuration values passed")
    uri = uri or config.get("general", "ldap_uri", "ldap://localhost")
    rootdn = rootdn or config.get("general", "ldap_rootdn", "dc=arkos-servers,dc=org")
    if not passwd:
        if os.path.isfile(os.path.join(sys.path[0], 'secrets.json')):
            secrets = os.path.join(sys.path[0], 'secrets.json')
        else:
            secrets = "/etc/arkos/secrets.json"
        with open(secrets, "r") as f:
            passwd = json.loads(f.read())
            if passwd.has_key("ldap"):
                passwd = passwd["ldap"]
            else:
                raise Exception("Admin LDAP credentials not found in secrets file")
        if passwd == "admin":
            passwd = change_admin_passwd(uri, rootdn, dn, config, secrets=secrets)
    c = ldap.initialize(uri)
    try:
        c.simple_bind_s("%s,%s" % (dn, rootdn), passwd)
    except ldap.INVALID_CREDENTIALS:
        raise Exception("Admin LDAP authentication failed.")
    if dn != "cn=admin":
        data = c.search_s("cn=admins,ou=groups,%s" % rootdn,
            ldap.SCOPE_SUBTREE, "(objectClass=*)", ["member"])[0][1]["member"]
        if "%s,%s" % (dn, rootdn) not in data:
            raise Exception("User is not an administrator") 
    return c

def change_admin_passwd(uri="", rootdn="", dn="cn=admin", config=None, passwd="admin", new_passwd="", secrets=""):
    from arkos.system import users, groups, services
    new_passwd = new_passwd or random_string()
    c = ldap_connect(uri, rootdn, dn, config, passwd)
    ldif = c.search_s("%s,%s" % (dn,rootdn),
        ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
    ldif = ldif[0][1]
    attrs = {
        "userPassword": hashpw(new_passwd, "crypt")
    }
    nldif = ldap.modlist.modifyModlist(ldif, attrs, ignore_oldexistent=1)
    c.modify_ext_s("%s,%s" % (dn,rootdn), nldif)
    with open(secrets, "r") as f:
        data = json.loads(f.read())
    data["ldap"] = new_passwd
    with open(secrets, "w") as f:
        f.write(json.dumps(data))
    with open("/etc/openldap/slapd.conf", "r") as f:
        data = f.readlines()
    with open("/etc/openldap/slapd.conf", "w") as f:
        for x in data:
            if x.startswith("rootpw"):
                x = "rootpw\t\t%s\n" % hashpw(new_passwd, "crypt")
            f.write(x)
    services.get("slapd").stop()
    for x in os.listdir("/etc/openldap/slapd.d"):
        if os.path.isdir(os.path.join("/etc/openldap/slapd.d", x)):
            shutil.rmtree(os.path.join("/etc/openldap/slapd.d", x))
        else:
            os.unlink(os.path.join("/etc/openldap/slapd.d", x))
    shell("slaptest -f /etc/openldap/slapd.conf -F /etc/openldap/slapd.d/")
    uid, gid = users.get_system("ldap").uid, groups.get_system("ldap").gid
    os.chown("/etc/openldap/slapd.d", uid, gid)
    for r, d, f in os.walk("/etc/openldap/slapd.d"):
        for x in d:
            os.chown(os.path.join(r, x), uid, gid)
        for x in f:
            os.chown(os.path.join(r, x), uid, gid)
    services.get("slapd").restart()
    try:
        c.simple_bind_s("%s,%s" % (dn, rootdn), new_passwd)
    except ldap.SERVER_DOWN:
        time.sleep(5)
    return new_passwd

def supervisor_connect():
    s = xmlrpclib.Server("http://localhost:9001/RPC2")
    return s.supervisor
