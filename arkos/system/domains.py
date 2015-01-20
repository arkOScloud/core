import ldap
import ldap.modlist

from arkos import config, conns


class Domain(object):
    name = ""
    rootdn = "dc=arkos-servers,dc=org"
    
    def __str__(self):
        return self.name
    
    def add(self):
        try:
            ldif = conns.LDAP.search_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBLIST, "(objectClass=*)", None)
            raise Exception("This domain is already present here")
        except ldap.NO_SUCH_OBJECT:
            pass
        ldif = {"virtualdomain": self.name, "objectClass": ["mailDomain", "top"]}
        conns.LDAP.add_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn),
            ldap.modlist.addModlist(ldif))
    
    def remove(self):
        conns.LDAP.delete_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn))

    def as_dict(self):
        return {"name": self.name}


def get(name=None):
    results = []
    qset = conns.LDAP.search_s("ou=domains,%s" % config.get("general", "ldap_rootdn", "dc=arkos-servers,dc=org"),
        ldap.SCOPE_SUBTREE, "virtualdomain=*", ["virtualdomain"])
    for x in qset:
        d = Domain()
        d.name = x[1]["virtualdomain"][0]
        d.rootdn = x[0].split("ou=domains,")[1]
        if d.name == name:
            return d
        results.append(d)
    return results
