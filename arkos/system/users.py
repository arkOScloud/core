import grp
import json
import ldap, ldap.modlist
import os
import pwd
import shutil
import sys

import groups

from arkos import conns, config, signals
from arkos.utilities import hashpw, shell


class User:
    def __init__(
            self, name="", first_name="", last_name=None, uid=0, domain="",
            rootdn="dc=arkos-servers,dc=org", mail=[], admin=False, sudo=False):
        self.name = str(name)
        self.first_name = str(first_name)
        self.last_name = None if last_name == None else str(last_name)
        self.uid = uid or get_next_uid()
        self.domain = str(domain)
        self.rootdn = str(rootdn)
        self.mail = [str(x) for x in mail]
        self.admin = admin
        self.sudo = sudo

    def add(self, passwd):
        try:
            ldif = conns.LDAP.search_s("uid=%s,ou=users,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
            raise Exception("A user with this name already exists")
        except ldap.NO_SUCH_OBJECT:
            pass

        # Create LDAP user with proper metadata
        ldif = {
            "objectClass": ["mailAccount", "inetOrgPerson", "posixAccount"],
            "givenName": self.first_name,
            "sn": self.last_name or "NONE",
            "displayName": self.first_name+" "+self.last_name,
            "cn": self.first_name+" "+self.last_name,
            "uid": self.name,
            "mail": [self.name+"@"+self.domain],
            "maildrop": self.name,
            "userPassword": hashpw(passwd, "crypt"),
            "gidNumber": "100",
            "uidNumber": str(self.uid),
            "homeDirectory": "/home/%s" % self.name,
            "loginShell": "/usr/bin/bash"
            }
        ldif = ldap.modlist.addModlist(ldif)
        signals.emit("users", "pre_add", self)
        conns.LDAP.add_s("uid=%s,ou=users,%s" % (self.name,self.rootdn), ldif)
        self.update_adminsudo()
        signals.emit("users", "post_add", self)

    def update(self, newpasswd=""):
        try:
            ldif = conns.LDAP.search_s("uid=%s,ou=users,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
        except ldap.NO_SUCH_OBJECT:
            raise Exception("This user does not exist")
        self.first_name = str(self.first_name)
        self.last_name = str(self.last_name)
        self.domain = str(self.domain)

        ldif = ldif[0][1]
        attrs = {
            "givenName": self.first_name,
            "sn": self.last_name,
            "displayName": "%s %s" % (self.first_name, self.last_name),
            "cn": "%s %s" % (self.first_name, self.last_name),
            "mail": self.mail
        }
        if newpasswd:
            attrs["userPassword"] = hashpw(newpasswd, "crypt")
        signals.emit("users", "pre_update", self)
        nldif = ldap.modlist.modifyModlist(ldif, attrs, ignore_oldexistent=1)
        conns.LDAP.modify_ext_s("uid=%s,ou=users,%s" % (self.name,self.rootdn), nldif)
        self.update_adminsudo()
        signals.emit("users", "post_update", self)

    def update_adminsudo(self):
        # Update the user's admin and sudo group settings in LDAP with current values
        ldif = conns.LDAP.search_s("cn=admins,ou=groups,%s" % self.rootdn,
            ldap.SCOPE_SUBTREE, "(objectClass=*)", None)[0][1]
        memlist = ldif["member"]

        if self.admin and "uid=%s,ou=users,%s"%(self.name,self.rootdn) not in memlist:
            memlist += ["uid=%s,ou=users,%s" % (self.name,self.rootdn)]
            conns.LDAP.modify_ext_s("cn=admins,ou=groups,%s" % self.rootdn,
                [(1, "member", None), (0, "member", memlist)])
        elif not self.admin and "uid=%s,ou=users,%s"%(self.name,self.rootdn) in memlist:
            memlist.remove("uid=%s,ou=users,%s" % (self.name,self.rootdn))
            conns.LDAP.modify_ext_s("cn=admins,ou=groups,%s" % self.rootdn,
                [(1, "member", None), (0, "member", memlist)])

        try:
            conns.LDAP.search_s("cn=%s,ou=sudo,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
            is_sudo = True
        except ldap.NO_SUCH_OBJECT:
            is_sudo = False

        if self.sudo and not is_sudo:
            nldif = {
                "objectClass": ["sudoRole", "top"],
                "cn": self.name,
                "sudoHost": "ALL",
                "sudoCommand": "ALL",
                "sudoUser": self.name,
                "sudoOption": "authenticate"
            }
            nldif = ldap.modlist.addModlist(nldif)
            conns.LDAP.add_s("cn=%s,ou=sudo,%s" % (self.name, self.rootdn), nldif)
        elif not self.sudo and is_sudo:
            conns.LDAP.delete_s("cn=%s,ou=sudo,%s" % (self.name, self.rootdn))

    def verify_passwd(self, passwd):
        # Validate the provided password against the hash stored in LDAP
        try:
            c = ldap.initialize("ldap://localhost")
            c.simple_bind_s("uid=%s,ou=users,%s" % (self.name, self.rootdn), passwd)
            data = c.search_s("cn=admins,ou=groups,%s" % self.rootdn,
                ldap.SCOPE_SUBTREE, "(objectClass=*)", ["member"])[0][1]["member"]
            if "uid=%s,ou=users,%s" % (self.name, self.rootdn) not in data:
                return False
            return True
        except ldap.INVALID_CREDENTIALS:
            return False

    def delete(self, delete_home=True):
        signals.emit("users", "pre_remove", self)
        self.admin, self.sudo = False, False
        self.update_adminsudo()
        if delete_home:
            hdir = conns.LDAP.search_s("uid=%s,ou=users,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", ["homeDirectory"])[0][1]["homeDirectory"][0]
            if os.path.exists(hdir):
                shutil.rmtree(hdir)
        conns.LDAP.delete_s("uid=%s,ou=users,%s" % (self.name,self.rootdn))
        signals.emit("users", "post_remove", self)

    def as_dict(self, ready=True):
        return {
            "id": self.uid,
            "name": self.name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "domain": self.domain,
            "admin": self.admin,
            "sudo": self.sudo,
            "mail_addresses": self.mail,
            "is_ready": ready
        }


class SystemUser:
    def __init__(self, name="", uid=0, groups=[]):
        self.name = name
        self.uid = uid or get_next_uid()
        self.groups = groups

    def add(self):
        shell("useradd -rm %s" % self.name)

    def update(self):
        for x in self.groups:
            shell("usermod -a -G %s %s" % (x, self.name))

    def update_password(self, passwd):
        shell("passwd %s" % self.name, stdin="%s\n%s\n" % (passwd,passwd))

    def delete(self):
        shell("userdel %s" % self.name)

    def as_dict(self):
        return {
            "id": self.uid,
            "name": self.name,
            "groups": self.groups
        }


def get(uid=None, name=None):
    r = []
    rootdn = config.get("general", "ldap_rootdn", "dc=arkos-servers,dc=org")
    ldap_users = conns.LDAP.search_s("ou=users,%s" % rootdn, ldap.SCOPE_SUBTREE,
        "(objectClass=inetOrgPerson)", None)
    for x in ldap_users:
        for y in x[1]:
            if y == "mail":
                continue
            if type(x[1][y]) == list and len(x[1][y]) == 1:
                x[1][y] = x[1][y][0]
        u = User(name=x[1]["uid"], uid=int(x[1]["uidNumber"]),
            first_name=x[1]["givenName"], last_name=x[1]["sn"] if x[1]["sn"] != "NONE" else None,
            mail=x[1]["mail"], domain=x[1]["mail"][0].split("@")[1],
            rootdn=x[0].split("ou=users,")[1])

        # Check if the user is a member of the admin or sudo groups
        try:
            conns.LDAP.search_s("cn=%s,ou=sudo,%s" % (u.name,u.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
            u.sudo = True
        except ldap.NO_SUCH_OBJECT:
            u.sudo = False
        memlist = conns.LDAP.search_s("cn=admins,ou=groups,%s" % u.rootdn,
            ldap.SCOPE_SUBTREE, "(objectClass=*)", None)[0][1]["member"]
        if "uid=%s,ou=users,%s"%(u.name,u.rootdn) in memlist:
            u.admin = True
        else:
            u.admin = False

        if u.uid == uid:
            return u
        elif name and u.name == name:
            return u
        r.append(u)
    return r if uid == None and name == None else None

def get_system(uid=None):
    r = []
    grps = groups.get_system()
    for x in pwd.getpwall():
        if x.pw_name == "root":
            continue
        su = SystemUser(name=x.pw_name, uid=x.pw_uid)
        for y in grps:
            if su.name in y.users:
                su.groups.append(y.name)
        if uid == su.name:
            return su
        r.append(su)
    return sorted(r, key=lambda x: x.uid) if not uid else None

def get_next_uid():
    return max([x.uid for x in get_system()]) + 1
