"""
Classes and functions to manage arkOS tracked services.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import random

from arkos import config, policies, signals, storage, security

COMMON_PORTS = [3000, 3306, 5222, 5223, 5232]


class SecurityPolicy:
    """
    An object representing an arkOS firewall policy for a service.

    SecurityPolicies are created for all websites, as well as for all apps
    that have port-based services registered in their metadata files. They
    are used to compute the proper values to put into the arkOS firewall
    (iptables) on regeneration or app update.
    """

    def __init__(self, type="", id="", name="", icon="", ports=[],
                 policy=2, addr=None):
        """
        Initialize the policy object.

        To create a new policy or to see more info about these parameters,
        see ``tracked_services.register()`` below.

        :param str type: Policy type ('website', 'app', etc)
        :param str id: Website or app ID
        :param str name: Display name to use in Security settings pane
        :param str icon: FontAwesome icon class name
        :param list ports: List of port tuples to allow/restrict
        :param int policy: Policy identifier
        :param str addr: Address and port (for websites)
        """
        self.type = type
        self.id = id
        self.name = name
        self.icon = icon
        self.ports = ports
        self.policy = policy
        self.addr = addr

    def save(self, fw=True):
        """
        Save changes to a security policy to disk.

        :param bool fw: Regenerate the firewall after save?
        """
        policies.set(self.type, self.id, self.policy)
        policies.save()
        if config.get("general", "firewall", True) and fw:
            security.regenerate_firewall(get())
        if not storage.policies.get("policies", self.id):
            storage.policies.add("policies", self)

    def remove(self, fw=True):
        """
        Remove a security policy from the firewall and config.

        You should probably use ``tracked_services.deregister()`` for this.

        :param bool fw: Regenerate the firewall after save?
        """
        policies.remove(self.type, self.id)
        policies.save()
        if config.get("general", "firewall", True) and fw:
            security.regenerate_firewall(get())
        storage.policies.remove("policies", self)

    @property
    def as_dict(self):
        """Return policy metadata as dict."""
        return {
            "type": self.type,
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "ports": self.ports,
            "policy": self.policy,
            "is_ready": True
        }

    @property
    def serialized(self):
        """Return serializable policy metadata as dict."""
        return self.as_dict


def get(id=None, type=None):
    """
    Get all security policies from cache storage.

    :param str id: App or website ID
    :param str type: Filter by type ('website', 'app', etc)
    """
    data = storage.policies.get("policies")
    if id or type:
        tlist = []
        for x in data:
            if x.id == id:
                return x
            elif x.type == type:
                tlist.append(x)
        if tlist:
            return tlist
        return []
    return data


def register(type, id, name, icon, ports, addr=None, policy=0,
             default_policy=2, fw=True):
    """
    Register a new security policy with the system.

    The ``ports`` parameter takes tuples of ports to manage, like so:

        ports = [('tcp', 8000), ('udp', 21500)]

    The ``policy`` parameter is an integer with the following meaning:

    0 = Restrict access from all outside hosts. (excludes loopback)
    1 = Restrict access to local networks only.
    2 = Allow access to all networks and ultimately the whole Internet.

    Addresses should be provided for websites, because multiple websites can
    be served from the same port (SNI) as long as the address is different.

    :param str type: Policy type ('website', 'app', etc)
    :param str id: Website or app ID
    :param str name: Display name to use in Security settings pane
    :param str icon: FontAwesome icon class name
    :param list ports: List of port tuples to allow/restrict
    :param str addr: Address (for websites)
    :param int policy: Policy identifier
    :param int default_policy: Application default policy to use on first init
    :param bool fw: Regenerate the firewall after save?
    """
    if not policy:
        policy = policies.get(type, id, default_policy)
    pget = get(type=type)
    if pget:
        for x in pget:
            if x.id == id:
                storage.policies.remove("policies", x)
    svc = SecurityPolicy(type, id, name, icon, ports, policy, addr)
    svc.save(fw)


def deregister(type, id="", fw=True):
    """
    Deregister a security policy.

    :param str type: Policy type ('website', 'app', etc)
    :param str id: Website or app ID
    :param bool fw: Regenerate the firewall after save?
    """
    for x in get(type=type):
        if not id:
            x.remove(fw=False)
        elif x.id == id:
            x.remove(fw=False)
            break
    if config.get("general", "firewall", True) and fw:
        security.regenerate_firewall(get())


def refresh_policies():
    """Recreate security policies based on what is stored in config."""
    svcs = get()
    newpolicies = {}
    for x in policies.get_all():
        if x == "custom":
            newpolicies["custom"] = policies.get_all("custom")
        for y in svcs:
            if x == y.type:
                if x not in newpolicies:
                    newpolicies[x] = {}
                for s in policies.get_all(x):
                    if s == y.id:
                        newpolicies[x][s] = policies.get(x, s)
    policies.config = newpolicies
    policies.save()


def is_open_port(port, addr=None, ignore_common=False):
    """
    Check if the specified port is taken by a tracked service or not.

    Addresses should be provided for websites, because multiple websites can
    be served from the same port (SNI) as long as the address is different.

    :param int port: Port number to check
    :param str addr: Address to check (for websites)
    :param bool ignore_common: Don't return False for commonly used ports?
    :returns: True if port is open
    :rtype bool:
    """
    data = get()
    ports = []
    for x in data:
        if addr and x.type == "website" and addr != x.addr:
            continue
        for y in x.ports:
            ports.append(int(y[1]))
    if not ignore_common:
        ports = ports + COMMON_PORTS
    return port not in ports


def get_open_port(ignore_common=False):
    """
    Get a random TCP port not currently in use by a tracked service.

    :param bool ignore_common: Don't exclude commonly used ports?
    :returns: Port number
    :rtype: int
    """
    data = get()
    ports = []
    for x in data:
        for y in x.ports:
            ports.append(int(y[1]))
    if not ignore_common:
        ports = ports + COMMON_PORTS
    r = random.randint(8001, 65534)
    return r if r not in ports else get_open_port()


def initialize():
    """Initialize security policy tracking."""
    policy = policies.get("arkos", "arkos", 2)
    port = [("tcp", int(config.get("genesis", "port")))]
    pol = SecurityPolicy("arkos", "arkos", "System Management (Genesis/APIs)",
                         "fa fa-desktop", port, policy)
    storage.policies.add("policies", pol)
    for x in policies.get_all("custom"):
        pol = SecurityPolicy("custom", x["id"], x["name"], x["icon"],
                             x["ports"], x["policy"])
        storage.policies.add("policies", pol)


def register_website(site):
    """Convenience function to register a website as tracked service."""
    register("website", site.id, getattr(site, "name", site.id),
             site.meta.icon if site.meta else "fa fa-globe",
             [("tcp", site.port)], site.addr)


def deregister_website(site):
    """Convenience function to deregister a website as tracked service."""
    deregister("website", site.id)


signals.add("tracked_services", "websites", "site_loaded", register_website)
signals.add("tracked_services", "websites", "site_installed", register_website)
signals.add("tracked_services", "websites", "site_removed", deregister_website)
