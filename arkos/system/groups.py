"""
Classes and functions for interacting with system management daemons.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE
"""

import grp
import ldap3

from arkos import conns, config, signals
from arkos.utilities import shell


class Group:
    """Class for managing arkOS groups in LDAP."""
    
    def __init__(self, name="", gid=0, users=[], rootdn="dc=arkos-servers,dc=org"):
        """
        Initialize the group object.

        :param str name: Username
        :param int gid: user ID number
        :param list users: List of user members
        :param str rootdn: Associated root DN in LDAP
        """
        self.name = str(name)
        self.gid = gid or get_next_gid()
        self.users = [str(user) for user in users]
        self.rootdn = rootdn
        
    @property
    def ldap_id(self):
        """Fetch LDAP ID."""
        qry = "cn={0},ou=groups,{1}"
        return qry.format(self.name, self.rootdn)

    def add(self):
        """Add the group to LDAP."""
        try:
            ldif = conns.LDAP.search_s("cn=%s,ou=groups,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
            raise Exception("A group with this name already exists")
        except ldap.NO_SUCH_OBJECT:
            pass
        ldif = {
            "objectClass": ["posixGroup", "top"],
            "cn": self.name,
            "gidNumber": str(self.gid),
            "memberUid": self.users
        }
        ldif = ldap.modlist.addModlist(ldif)
        signals.emit("groups", "pre_add", self)
        conns.LDAP.add_s("cn=%s,ou=groups,%s" % (self.name,self.rootdn), ldif)
        signals.emit("groups", "post_add", self)

    def update(self):
        """Update a group object in LDAP. Change params on the object first."""
        try:
            ldif = conns.LDAP.search_s("cn=%s,ou=groups,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
        except ldap.NO_SUCH_OBJECT:
            raise Exception("This group does not exist")

        ldif = ldap.modlist.modifyModlist(ldif[0][1], {"memberUid": self.users},
            ignore_oldexistent=1)
        signals.emit("groups", "pre_update", self)
        conns.LDAP.modify_ext_s("cn=%s,ou=groups,%s" % (self.name,self.rootdn), ldif)
        signals.emit("groups", "post_update", self)

    def delete(self):
        """Delete group."""
        
        signals.emit("groups", "pre_remove", self)
        conns.LDAP.delete_s("cn=%s,ou=groups,%s" % (self.name,self.rootdn))
        signals.emit("groups", "post_remove", self)

    @property
    def as_dict(self, ready=True):
        """Return group metadata as dict."""
        return {
            "id": self.gid,
            "name": self.name,
            "users": self.users,
            "is_ready": ready
        }

    @property
    def serialized(self):
        """Return serializable group metadata as dict."""
        return self.as_dict


class SystemGroup:
    """Class for managing system groups."""
    
    def __init__(self, name="", gid=0, users=[]):
        """
        Initialize the user object.

        :param str name: Group name
        :param int gid: group ID number
        :param list users: List of user members
        """
        self.name = name
        self.gid = gid
        self.users = users

    def add(self):
        """Add group."""
        shell("groupadd {0}".format(self.name))
        self.update()
        for x in grp.getgrall():
            if x.gr_name == self.name:
                self.gid = x.gr_gid

    def update(self):
        """Update group members."""
        for x in self.users:
            shell("usermod -a -G {0} {1}".format(self.name, x))

    def delete(self):
        """Delete group."""
        shell("groupdel {0}".format(self.name))


def get(gid=None):
    """
    Get all LDAP groups.

    :param str gid: ID of single group to fetch
    :returns: Group(s)
    :rtype: Group or list thereof
    """
    r = []
    qry = "ou=groups,{0}".format(config.get("general", "ldap_rootdn",
                                            "dc=arkos-servers,dc=org"))
    search = conns.LDAP.search_s(qry, ldap.SCOPE_SUBTREE,
                                 "(objectClass=posixGroup)", None)
    for x in search:
        for y in x[1]:
            if type(x[1][y]) == list and len(x[1][y]) == 1 \
                    and y != "memberUid":
                x[1][y] = x[1][y][0]
        g = Group(x[1]["cn"], int(x[1]["gidNumber"]),
                  x[1].get("memberUid", []), x[0].split("ou=groups,")[1])
        if g.gid == gid:
            return g
        r.append(g)
    return r if not gid else Non

def get_system(gid=None):
    """
    Get all system groups.

    :param str gid: ID of single group to fetch
    :returns: SystemGroup(s)
    :rtype: SystemGroup or list thereof
    """
    r = []
    for x in grp.getgrall():
        g = SystemGroup(name=x.gr_name, gid=x.gr_gid, users=x.gr_mem)
        if gid == g.name:
            return g
        r.append(g)
    return r if not gid else None

def get_next_gid():
    """Get the next available group ID number in sequence."""
    return max([x.gid for x in get_system()]) + 1
