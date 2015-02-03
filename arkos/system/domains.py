import ldap
import ldap.modlist

from arkos import config, conns
from arkos.system import users


class Domain:
    def __init__(self, name, rootdn="dc=arkos-servers,dc=org"):
        self.name = str(name)
        self.rootdn = rootdn
    
    def __str__(self):
        return self.name
    
    def add(self):
        try:
            ldif = conns.LDAP.search_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBTREE, "(objectClass=*)", None)
            raise Exception("This domain is already present here")
        except ldap.NO_SUCH_OBJECT:
            pass
        ldif = {"virtualdomain": self.name, "objectClass": ["mailDomain", "top"]}
        conns.LDAP.add_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn),
            ldap.modlist.addModlist(ldif))
    
    def remove(self):
        if self.name in [x.domain for x in users.get()]:
            raise Exception("A user is still using this domain")
        conns.LDAP.delete_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn))

    def as_dict(self, ready=True):
        return {"id": self.name, "is_ready": ready}


def get(id=None):
    results = []
    qset = conns.LDAP.search_s("ou=domains,%s" % config.get("general", "ldap_rootdn", "dc=arkos-servers,dc=org"),
        ldap.SCOPE_SUBTREE, "virtualdomain=*", ["virtualdomain"])
    for x in qset:
        d = Domain(name=x[1]["virtualdomain"][0], rootdn=x[0].split("ou=domains,")[1])
        if d.name == id:
            return d
        results.append(d)
    return results
