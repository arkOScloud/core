"""
Classes and functions for managing LDAP and system users.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import ldap
import ldap.modlist
import os
import pwd
import shutil

from . import groups

from arkos import conns, config, logger, signals
from arkos.utilities import b, errors, hashpw, shell


class User:
    """Class for managing arkOS users in LDAP."""

    def __init__(
            self, name="", first_name="", last_name=None, uid=0, domain="",
            rootdn="dc=arkos-servers,dc=org", mail=[], admin=False,
            sudo=False):
        """
        Initialize the user object.

        :param str name: Username
        :param str first_name: First name or pseudonym of user
        :param str last_name: Last name of user, or None
        :param int uid: user ID number
        :param str domain: Associated domain name
        :param str rootdn: Associated root DN in LDAP
        :param list mail: List of mail addresses and aliases
        :param bool admin: Is admin user?
        :param bool sudo: Can execute with sudo?
        """
        self.name = name
        self.first_name = first_name
        self.last_name = None if last_name is None else last_name
        self.uid = uid or get_next_uid()
        self.domain = domain
        self.rootdn = rootdn
        self.mail = [x for x in mail]
        self.admin = admin
        self.sudo = sudo

    @property
    def ldap_id(self):
        """Fetch LDAP ID."""
        qry = "uid={0},ou=users,{1}"
        return qry.format(self.name, self.rootdn)

    def add(self, passwd):
        """
        Add the user to LDAP.

        :param str passwd: user password to set
        """
        try:
            ldif = conns.LDAP.search_s(
                self.ldap_id, ldap.SCOPE_BASE, "(objectClass=*)", None)
            logger.error("Roles", "A user with this name already exists")
            raise errors.InvalidConfigError(
                "A user with this name already exists")
        except ldap.NO_SUCH_OBJECT:
            pass

        # Create LDAP user with proper metadata
        ldif = {
            "objectClass": [b"mailAccount", b"inetOrgPerson", b"posixAccount"],
            "givenName": [b(self.first_name)],
            "sn": [b(self.last_name)] if self.last_name else [b"NONE"],
            "displayName": [b(self.first_name + " " + self.last_name)],
            "cn": [b(self.first_name + (" " + self.last_name or ""))],
            "uid": [b(self.name)],
            "mail": [b(self.name + "@" + self.domain)],
            "maildrop": [b(self.name)],
            "userPassword": [b(hashpw(passwd))],
            "gidNumber": [b"100"],
            "uidNumber": [b(str(self.uid))],
            "homeDirectory": [b("/home/" + self.name)],
            "loginShell": [b"/usr/bin/bash"]
            }
        ldif = ldap.modlist.addModlist(ldif)
        signals.emit("users", "pre_add", self)
        logger.debug("Roles", "Adding user: {0}".format(self.ldap_id))
        conns.LDAP.add_s(self.ldap_id, ldif)
        modes = ["admin" if self.admin else "", "sudo" if self.sudo else ""]
        msg = "Setting user modes: {0}".format(", ".join(modes))
        logger.debug("Roles", msg)
        self.update_adminsudo()
        signals.emit("users", "post_add", self)

    def update(self, newpasswd=""):
        """
        Update a user's object in LDAP. Change params on the object first.

        To change password, do so via the ``newpasswd`` param here.

        :param str newpasswd: new password to set
        """
        try:
            ldif = conns.LDAP.search_s(self.ldap_id, ldap.SCOPE_SUBTREE,
                                       "(objectClass=*)", None)
        except ldap.NO_SUCH_OBJECT:
            raise errors.InvalidConfigError(
                "Roles", "This user does not exist")

        ldif = ldif[0][1]
        attrs = {
            "givenName": [b(self.first_name)],
            "sn": [b(self.last_name or "")],
            "displayName": [b(self.first_name + " " + self.last_name)],
            "cn": [b(self.first_name + (" " + self.last_name or ""))],
            "mail": [b(x) for x in self.mail]
        }
        if newpasswd:
            attrs["userPassword"] = [b(hashpw(newpasswd))]
        signals.emit("users", "pre_update", self)
        nldif = ldap.modlist.modifyModlist(ldif, attrs, ignore_oldexistent=1)
        conns.LDAP.modify_s(self.ldap_id, nldif)
        self.update_adminsudo()
        signals.emit("users", "post_update", self)

    def update_adminsudo(self):
        """Update the user's admin and sudo group settings in LDAP."""
        ldif = conns.LDAP.search_s(
            "cn=admins,ou=groups,{0}".format(self.rootdn),
            ldap.SCOPE_SUBTREE, "(objectClass=*)", None)[0][1]
        memlist = ldif["member"]
        ldif_vals = [(1, "member", None), (0, "member", memlist)]

        if self.admin and b(self.ldap_id) not in memlist:
            memlist += [b(self.ldap_id)]
            conns.LDAP.modify_s(
                "cn=admins,ou=groups,{0}".format(self.rootdn), ldif_vals)
        elif not self.admin and self.ldap_id in memlist:
            memlist.remove(self.ldap_id)
            conns.LDAP.modify_s(
                "cn=admins,ou=groups,{0}".format(self.rootdn), ldif_vals)

        try:
            conns.LDAP.search_s(
                "cn={0},ou=sudo,{1}".format(
                    self.name, self.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
            is_sudo = True
        except ldap.NO_SUCH_OBJECT:
            is_sudo = False

        if self.sudo and not is_sudo:
            nldif = {
                "objectClass": [b"sudoRole", b"top"],
                "cn": [b(self.name)],
                "sudoHost": b"ALL",
                "sudoCommand": b"ALL",
                "sudoUser": [b(self.name)],
                "sudoOption": b"authenticate"
            }
            nldif = ldap.modlist.addModlist(nldif)
            conns.LDAP.add_s(
                "cn=" + self.name + ",ou=sudo," + self.rootdn, nldif)
        elif not self.sudo and is_sudo:
            conns.LDAP.delete_s(
                "cn=" + self.name + ",ou=sudo," + self.rootdn)

    def verify_passwd(self, passwd):
        """
        Validate the provided password against the hash stored in LDAP.

        :param str passwd: password to check
        """
        try:
            c = ldap.initialize("ldap://localhost")
            c.simple_bind_s(self.ldap_id, passwd)
            data = c.search_s("cn=admins,ou=groups," + self.rootdn,
                              ldap.SCOPE_SUBTREE, "(objectClass=*)",
                              ["member"])[0][1]["member"]
            if b(self.ldap_id) not in data:
                return False
            return True
        except ldap.INVALID_CREDENTIALS:
            return False

    def delete(self, delete_home=True):
        """
        Delete user.

        :param bool delete_home: Delete the user's home directory too?
        """
        signals.emit("users", "pre_remove", self)
        self.admin, self.sudo = False, False
        self.update_adminsudo()
        if delete_home:
            hdir = conns.LDAP.search_s(self.ldap_id, ldap.SCOPE_SUBTREE,
                                       "(objectClass=*)", ["homeDirectory"])
            hdir = hdir[0][1]["homeDirectory"][0]
            if os.path.exists(hdir):
                shutil.rmtree(hdir)
        conns.LDAP.delete_s(self.ldap_id)
        signals.emit("users", "post_remove", self)

    @property
    def as_dict(self, ready=True):
        """Return user metadata as dict."""
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

    @property
    def serialized(self):
        """Return serializable user metadata as dict."""
        return self.as_dict


class SystemUser:
    """Class for managing system user records."""

    def __init__(self, name="", uid=0, groups=[]):
        """
        Initialize system user object.

        :param str name: username
        :param int uid: user ID number
        :param list groups: groups this user is a member of
        """
        self.name = name
        self.uid = uid or get_next_uid()
        self.groups = groups

    def add(self):
        """Add user."""
        shell("useradd -rm {0}".format(self.name))

    def update(self):
        """Update user groups."""
        for x in self.groups:
            shell("usermod -a -G {0} {1}".format(x, self.name))

    def update_password(self, passwd):
        """
        Set password.

        :param str passwd: password to set
        """
        shell("passwd {0}".format(self.name),
              stdin="{0}\n{1}\n".format(passwd, passwd))

    def delete(self):
        """Delete user."""
        shell("userdel {0}".format(self.name))

    @property
    def as_dict(self):
        """Return system user metadata as dict."""
        return {
            "id": self.uid,
            "name": self.name,
            "groups": self.groups
        }

    @property
    def serialized(self):
        """Return serialized system user metadata as dict."""
        return self.as_dict


def get(uid=None, name=None):
    """
    Get all LDAP users.

    :param str id: ID of single user to fetch
    :param str name: username of single user to fetch
    :returns: User(s)
    :rtype: User or list thereof
    """
    r = []
    rootdn = config.get("general", "ldap_rootdn", "dc=arkos-servers,dc=org")
    ldap_users = conns.LDAP.search_s("ou=users," + rootdn, ldap.SCOPE_SUBTREE,
                                     "(objectClass=inetOrgPerson)", None)
    for x in ldap_users:
        for y in x[1]:
            if y == "mail":
                continue
            if type(x[1][y]) == list and len(x[1][y]) == 1:
                x[1][y] = x[1][y][0]
        u = User(x[1]["uid"].decode(), x[1]["givenName"].decode(),
                 x[1]["sn"].decode() if x[1]["sn"] != b"NONE" else None,
                 int(x[1]["uidNumber"]),
                 x[1]["mail"][0].split(b"@")[1].decode(),
                 x[0].split("ou=users,")[1],
                 [z.decode() for z in x[1]["mail"]])

        # Check if the user is a member of the admin or sudo groups
        try:
            conns.LDAP.search_s("cn={0},ou=sudo,{1}".format(u.name, u.rootdn),
                                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
            u.sudo = True
        except ldap.NO_SUCH_OBJECT:
            u.sudo = False
        memlist = conns.LDAP.search_s("cn=admins,ou=groups,{0}"
                                      .format(u.rootdn), ldap.SCOPE_SUBTREE,
                                      "(objectClass=*)", None)[0][1]["member"]
        if b("uid={0},ou=users,{1}".format(u.name, u.rootdn)) in memlist:
            u.admin = True
        else:
            u.admin = False

        if u.uid == uid:
            return u
        elif name and u.name == name:
            return u
        r.append(u)
    return r if uid is None and name is None else None


def get_system(uid=None):
    """
    Get all system users.

    :param str id: ID of single user to fetch
    :param str name: username of single user to fetch
    :returns: SystemUser(s)
    :rtype: SystemUser or list thereof
    """
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
    """Get the next available user ID number in sequence."""
    return max([x.uid for x in get_system()]) + 1
