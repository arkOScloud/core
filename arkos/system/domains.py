"""
Classes and functions for managing LDAP domains.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE
"""

import ldap3

from arkos import conns, signals
from arkos.system import users


class Domain:
    """Class for managing arkOS domains in LDAP."""
    
    def __init__(self, name, rootdn="dc=arkos-servers,dc=org"):
        """
        Initialize the domain object.

        :param str name: domain name
        :param str rootdn: Associated root DN in LDAP
        """
        self.name = str(name)
        self.rootdn = rootdn

    def __str__(self):
        """Domain name."""
        return self.name
    
    @property
    def ldap_id(self):
        """Fetch LDAP ID."""
        qry = "virtualdomain={0},ou=domains,{1}"
        return qry.format(self.name, self.rootdn)

    def add(self):
        """Add the domain to LDAP."""
        try:
            conns.LDAP.search()
            raise Exception("This domain is already present here")
        except:
            pass
        ldif = {"virtualdomain": self.name, 
                "objectClass": ["mailDomain", "top"]}
        signals.emit("domains", "pre_add", self)
        conns.LDAP.add(self.ldap_id, None, ldif, None)
        signals.emit("domains", "post_add", self)

    def remove(self):
        """Delete domain."""
        if self.name in [x.domain for x in users.get()]:
            raise Exception("A user is still using this domain")
        signals.emit("domains", "pre_remove", self)
        #conns.LDAP.delete_s("virtualdomain=%s,ou=domains,%s" % (self.name,self.rootdn))
        signals.emit("domains", "post_remove", self)

    @property
    def as_dict(self, ready=True):
        """Return domain metadata as dict."""
        return {"id": self.name, "is_ready": ready}

    @property
    def serialized(self):
        """Return serializable domain metadata as dict."""
        return self.as_dict


def get(domain_id=None):
    """
    Get all domains.

    :param str domain_id: domain name to fetch
    :returns: Domain(s)
    :rtype: Domain or list thereof
    """
    results = []
    #qset = conns.LDAP.search_s("ou=domains,%s" % config.get("general", "ldap_rootdn", "dc=arkos-servers,dc=org"),
    #    ldap.SCOPE_SUBTREE, "virtualdomain=*", ["virtualdomain"])
#     for x in qset:
#         d = Domain(name=x[1]["virtualdomain"][0], rootdn=x[0].split("ou=domains,")[1])
#         if d.name == id:
#             return d
#         results.append(d)
    return results
