import grp
import ldap
import ldap.modlist

from arkos import conns, config
from arkos.utilities import shell


class Group:
    def __init__(self, name="", gid=0, users=[], rootdn="dc=arkos-servers,dc=org"):
        self.name = str(name)
        self.gid = gid or get_next_gid()
        self.users = [str(user) for user in users]
        self.rootdn = rootdn
    
    def add(self):
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
        conns.LDAP.add_s("cn=%s,ou=groups,%s" % (self.name,self.rootdn), ldif)
    
    def update(self):
        try:
            ldif = conns.LDAP.search_s("cn=%s,ou=groups,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
        except ldap.NO_SUCH_OBJECT:
            raise Exception("This group does not exist")

        ldif = ldap.modlist.modifyModlist(ldif[0][1], {"memberUid": self.users}, 
            ignore_oldexistent=1)
        conns.LDAP.modify_ext_s("cn=%s,ou=groups,%s" % (self.name,self.rootdn), ldif)
    
    def delete(self):
        conns.LDAP.delete_s("cn=%s,ou=groups,%s" % (self.name,self.rootdn))
    
    def as_dict(self, ready=True):
        return {
            "id": self.gid,
            "name": self.name,
            "users": self.users,
            "is_ready": ready
        }


class SystemGroup:    
    def __init__(self, name="", gid=0, users=[]):
        self.name = name
        self.gid = gid
        self.users = users

    def add(self):
        shell("groupadd %s" % self.name)
        self.update()
        for x in grp.getgrall():
            if x.gr_name == self.name:
                self.gid = x.gr_gid
    
    def update(self):
        for x in self.users:
            shell("usermod -a -G %s %s" % (self.name, x))

    def delete(self):
        shell("groupdel %s" % self.name)


def get(gid=None):
    r = []
    for x in conns.LDAP.search_s("ou=groups,%s" % config.get("general", "ldap_rootdn", "dc=arkos-servers,dc=org"), 
            ldap.SCOPE_SUBTREE, "(objectClass=posixGroup)", None):
        for y in x[1]:
            if type(x[1][y]) == list and len(x[1][y]) == 1 and y != "memberUid":
                x[1][y] = x[1][y][0]
        g = Group(name=x[1]["cn"], gid=int(x[1]["gidNumber"]), users=x[1].get("memberUid") or [],
            rootdn=x[0].split("ou=groups,")[1])
        if g.gid == gid:
            return g
        r.append(g)
    return r if not gid else None

def get_system(gid=None):
    r = []
    for x in grp.getgrall():
        g = SystemGroup(name=x.gr_name, gid=x.gr_gid, users=x.gr_mem)
        if gid == g.name:
            return g
        r.append(g)
    return r if not gid else None

def get_next_gid():
    return max([x.gid for x in get_system()]) + 1
