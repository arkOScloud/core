"""
Classes and functions for interacting with system management daemons.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import ldap
import ldap.modlist
import xmlrpc.client


from .utilities import errors
from dbus import SystemBus, Interface


class ConnectionsManager:
    """Manages arkOS connections to system-level processes via their APIs."""

    def __init__(self, config, secrets):
        self.config = config
        self.secrets = secrets

    def connect(self):
        """Initialize the connections."""
        self.connect_services()
        self.connect_ldap()

    def connect_services(self):
        self.DBus = SystemBus()
        self.SystemD = self.SystemDConnect(
            "/org/freedesktop/systemd1", "org.freedesktop.systemd1.Manager")
        self.Supervisor = supervisor_connect()

    def connect_ldap(self):
        self.LDAP = ldap_connect(
            config=self.config, passwd=self.secrets.get("ldap")
        )

    def SystemDConnect(self, path, interface):
        systemd = self.DBus.get_object("org.freedesktop.systemd1", path)
        return Interface(systemd, dbus_interface=interface)


def ldap_connect(
        uri="", rootdn="", dn="cn=admin", config=None, passwd="",
        conn_type=""):
    """
    Initialize a connection to arkOS LDAP.

    :param str uri: LDAP host URI
    :param str rootdn: Root DN
    :param str dn: User DN
    :param Config config: arkOS config to use for default values
    :param str passwd: Password to use to validate credentials
    :returns: LDAP connection object
    """
    if not all([uri, rootdn, dn]) and not config:
        raise errors.InvalidConfigError("No LDAP values passed")
    uri = uri or config.get("general", "ldap_uri")
    rootdn = rootdn or config.get("general", "ldap_rootdn")
    conn_type = conn_type or config.get("general", "ldap_conntype")

    if conn_type == "dynamic":
        c = ldap.ldapobject.ReconnectLDAPObject(
            uri, retry_max=3, retry_delay=5.0)
    else:
        c = ldap.initialize(uri)

    try:
        c.simple_bind_s("{0},{1}".format(dn, rootdn), passwd)
    except ldap.INVALID_CREDENTIALS:
        raise errors.ConnectionError("LDAP", "Invalid username/password")
    except Exception as e:
        raise errors.ConnectionError("LDAP") from e
    if dn != "cn=admin":
        data = c.search_s("cn=admins,ou=groups,{0}".format(rootdn),
                          ldap.SCOPE_SUBTREE, "(objectClass=*)",
                          ["member"])[0][1]["member"]
        if "{0},{1}".format(dn, rootdn) not in data:
            raise errors.ConnectionError("LDAP", "Not an administrator")
    return c


def supervisor_connect():
    """
    Initialize a connection to Supervisor via XML-RPC API.

    :returns: XML-RPC connection object
    """
    try:
        s = xmlrpc.client.Server("http://localhost:9001/RPC2")
        return s.supervisor
    except Exception as e:
        raise errors.ConnectionError("Supervisor") from e
