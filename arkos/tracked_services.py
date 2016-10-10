"""
Classes and functions to manage arkOS tracked services.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import glob
import miniupnpc
import random

from arkos import config, logger, policies, signals, storage, security
from arkos.messages import Notification
from arkos.utilities import errors, test_port

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
        if self.type == "custom":
            for x in policies.get_all("custom"):
                if self.id == x["id"]:
                    policies.remove_list("custom", x)
                    break
            policies.append(
                "custom",
                {"id": self.id, "name": self.name, "icon": self.icon,
                 "ports": self.ports, "policy": self.policy}
            )
        else:
            policies.set(self.type, self.id, self.policy)
        policies.save()
        storage.policies[self.id] = self
        if config.get("general", "firewall") and fw:
            security.regenerate_firewall(get())

    def remove(self, fw=True):
        """
        Remove a security policy from the firewall and config.

        You should probably use ``tracked_services.deregister()`` for this.

        :param bool fw: Regenerate the firewall after save?
        """
        if self.type == "custom":
            for x in policies.get_all("custom"):
                if self.id == x["id"]:
                    policies.remove_list("custom", x)
                    break
        else:
            policies.remove(self.type, self.id)
        policies.save()
        if self.id in storage.policies:
            del storage.policies[self.id]
        if config.get("general", "firewall") and fw:
            security.regenerate_firewall(get())

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


class PortConflictError(errors.Error):
    """Raised when an address and port requested are not available."""

    def __init__(self, port, domain):
        self.port = port
        self.domain = domain

    def __str__(self):
        return ("This port is taken by another site or service, "
                "please choose another")


def get(id=None, type=None):
    """
    Get all security policies from cache storage.

    :param str id: App or website ID
    :param str type: Filter by type ('website', 'app', etc)
    """
    data = storage.policies
    if id:
        return data.get(id)
    if type:
        return filter(lambda x: x.type == type, data.values())
    return data.values()


def register(type, id, name, icon, ports, domain=None, policy=0,
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
    :param str domain: Address (for websites)
    :param int policy: Policy identifier
    :param int default_policy: Application default policy to use on first init
    :param bool fw: Regenerate the firewall after save?
    """
    if not policy:
        policy = policies.get(type, id, default_policy)
    svc = SecurityPolicy(type, id, name, icon, ports, policy, domain)
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
    if config.get("general", "firewall") and fw:
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


def is_open_port(port, domain=None, ignore_common=False):
    """
    Check if the specified port is taken by a tracked service or not.

    Addresses should be provided for websites, because multiple websites can
    be served from the same port (SNI) as long as the address is different.

    :param int port: Port number to check
    :param str domain: Address to check (for websites)
    :param bool ignore_common: Don't return False for commonly used ports?
    :returns: True if port is open
    :rtype bool:
    """
    data = get()
    ports = []
    for x in data:
        if domain and x.type == "website" and domain != x.addr:
            continue
        for y in x.ports:
            ports.append(int(y[1]))
    if not ignore_common:
        ports = ports + COMMON_PORTS
    return port not in ports


def _upnp_igd_connect():
    upnpc = miniupnpc.UPnP()
    upnpc.discoverdelay = 3000
    devs = upnpc.discover()
    if devs == 0:
        msg = "Failed to connect to uPnP IGD: no devices found"
        logger.warning("TrackedSvcs", msg)
        return
    try:
        upnpc.selectigd()
    except Exception as e:
        msg = "Failed to connect to uPnP IGD: {0}"
        logger.warning("TrackedSvcs", msg.format(str(e)))
    return upnpc


def open_upnp(port):
    """
    Open and forward a port with the local uPnP IGD.

    :param tuple port: Port protocol and number
    """
    upnpc = _upnp_igd_connect()
    if not upnpc:
        return
    if upnpc.getspecificportmapping(port[1], port[0].upper()):
        try:
            upnpc.deleteportmapping(port[1], port[0].upper())
        except:
            pass
    try:
        pf = 'arkOS Port Forwarding: {0}'
        upnpc.addportmapping(port[1], port[0].upper(), upnpc.lanaddr, port[1],
                             pf.format(port[1]), '')
    except Exception as e:
        msg = "Failed to register {0} with uPnP IGD: {1}"
        logger.error("TrackedSvcs", msg.format(port, str(e)))


def close_upnp(port):
    """
    Remove forwarding of a port with the local uPnP IGD.

    :param tuple port: Port protocol and number
    """
    upnpc = _upnp_igd_connect()
    if not upnpc:
        return
    if upnpc.getspecificportmapping(port[1], port[0].upper()):
        try:
            upnpc.deleteportmapping(port[1], port[0].upper())
        except:
            pass


def initialize_upnp(svcs):
    """
    Initialize uPnP port forwarding with the IGD.

    :param SecurityPolicy svcs: SecurityPolicies to open
    """
    upnpc = _upnp_igd_connect()
    if not upnpc:
        return
    for svc in svcs:
        if svc.policy != 2:
            continue
        for protocol, port in svc.ports:
            if upnpc.getspecificportmapping(port, protocol.upper()):
                try:
                    upnpc.deleteportmapping(port, protocol.upper())
                except:
                    pass
            try:
                pf = 'arkOS Port Forwarding: {0}'
                upnpc.addportmapping(port, protocol.upper(), upnpc.lanaddr,
                                     port, pf.format(port), '')
            except Exception as e:
                msg = "Failed to register {0} with uPnP IGD: {1}"\
                      .format(port, str(e))
                logger.warning("TrackedSvcs", msg)


def open_all_upnp(ports):
    """
    Open and forward multiple ports with the local uPnP IGD.

    :param list ports: List of port objects to open
    """
    upnpc = _upnp_igd_connect()
    if not upnpc:
        return
    for port in [x for x in ports]:
        if upnpc.getspecificportmapping(port[1], port[0].upper()):
            try:
                upnpc.deleteportmapping(port[1], port[0].upper())
            except:
                pass
        try:
            pf = 'arkOS Port Forwarding: {0}'
            upnpc.addportmapping(port[1], port[0].upper(), upnpc.lanaddr,
                                 port[1], pf.format(port[1]), '')
        except Exception as e:
            msg = "Failed to register {0} with uPnP IGD: {1}"
            logger.error("TrackedSvcs", msg.format(port, str(e)))


def close_all_upnp(ports):
    """
    Remove forwarding of multiple ports with the local uPnP IGD.

    :param list ports: List of port objects to close
    """
    upnpc = _upnp_igd_connect()
    if not upnpc:
        return
    for port in [x for x in ports]:
        if upnpc.getspecificportmapping(port[1], port[0].upper()):
            try:
                upnpc.deleteportmapping(port[1], port[0].upper())
            except:
                pass


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
    # arkOS
    policy = policies.get("arkos", "arkos", 2)
    port = [("tcp", int(config.get("genesis", "port")))]
    pol = SecurityPolicy("arkos", "arkos", "System Management (Genesis/APIs)",
                         "server", port, policy)
    storage.policies[pol.id] = pol

    # uPNP
    policy = policies.get("arkos", "upnp", 1)
    pol = SecurityPolicy("arkos", "upnp", "uPnP Firewall Comms",
                         "server", [("udp", 1900)], policy)
    if config.get("general", "enable_upnp"):
        storage.policies[pol.id] = pol

    # ACME dummies
    for x in glob.glob("/etc/nginx/sites-enabled/acme-*"):
        acme_name = x.split("/etc/nginx/sites-enabled/acme-")[1]
        pol = SecurityPolicy(
            "acme", acme_name, "{0} (ACME Validation)".format(acme_name),
            "globe", [('tcp', 80)], 2
        )
        storage.policies[pol.id] = pol

    for x in policies.get_all("custom"):
        pol = SecurityPolicy("custom", x["id"], x["name"], x["icon"],
                             x["ports"], x["policy"])
        storage.policies[pol.id] = pol


def register_website(site):
    """Convenience function to register a website as tracked service."""
    register("website", site.id, getattr(site, "name", site.id),
             site.app.icon if site.app else "globe",
             [("tcp", site.port)], site.domain)


def deregister_website(site):
    """Convenience function to deregister a website as tracked service."""
    deregister("website", site.id)


def open_upnp_site(site):
    """Convenience function to register a website with uPnP."""
    if config.get("general", "enable_upnp"):
        open_upnp(("tcp", site.port))
    domain = site.domain
    if domain == "localhost" or domain.endswith(".local"):
        domain = None
    try:
        test_port(config.get("general", "repo_server"), site.port, domain)
    except:
        msg = ("Port {0} and/or domain {1} could not be tested."
               " Make sure your ports are properly forwarded and"
               " that your domain is properly set up.")\
               .format(site.port, site.domain)
        Notification("error", "TrackedSvcs", msg).send()


def close_upnp_site(site):
    """Convenience function to deregister a website with uPnP."""
    if config.get("general", "enable_upnp"):
        close_upnp(("tcp", site.port))


signals.add("tracked_services", "websites", "site_loaded", register_website)
signals.add("tracked_services", "websites", "site_installed", register_website)
signals.add("tracked_services", "websites", "site_installed", open_upnp_site)
signals.add("tracked_services", "websites", "site_removed", deregister_website)
signals.add("tracked_services", "websites", "site_removed", close_upnp_site)
