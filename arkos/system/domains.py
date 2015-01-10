import ldap
import ldap.modlist

from arkos.connections import db_ldap


class Domain(object):
    name = ""
    rootdn = "dc=arkos-servers,dc=org"
    
    def __str__(self):
        return self.name
    
    def add(self):
        try:
            ldif = db_ldap.search_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn),
                ldap.SCOPE_SUBLIST, "(objectClass=*)", None)
            raise Exception("This domain is already present here")
        except ldap.NO_SUCH_OBJECT:
            continue
        ldif = {"virtualdomain": self.name, "objectClass": ["mailDomain", "top"]}
        db_ldap.add_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn),
            ldap.modlist.addModlist(ldif))
    
    def remove_domain(self):
        db_ldap.delete_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn))


def get(self, name=None):
    results = []
    qset = db_ldap.search_s("ou=domains,%s" % self.rootdn,
        ldap.SCOPE_SUBTREE, "virtualdomain=*", ["virtualdomain"])
    for x in qset:
        d = Domain()
        d.name = x[1]["virtualdomain"][0]
        d.rootdn = x[0].split("ou=domains,")[1]
        if d.name == name:
            return d
        results.append(d)
    return results
