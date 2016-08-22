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

from dbus import SystemBus, Interface


class ConnectionsManager:
    """Manages arkOS connections to system-level processes via their APIs."""

    def connect(self, config, secrets):
        """
        Initialize the connections.

        :param Config config: arkOS config
        :param Config secrets: arkOS secrets
        """
        self.config = config
        self.secrets = secrets
        self.DBus = SystemBus()
        self.SystemD = self.SystemDConnect("/org/freedesktop/systemd1",
                                           "org.freedesktop.systemd1.Manager")
        self.LDAP = ldap_connect(config=config, passwd=secrets.get("ldap"))
        self.Supervisor = supervisor_connect()

    def SystemDConnect(self, path, interface):
        """
        Initialize a DBus interface to a systemd resource.

        :param str path: Path to systemd object
        :param str interface: Name of resource
        :returns: DBus ``Interface``
        """
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
        raise Exception("No configuration values passed")
    uri = uri or config.get("general", "ldap_uri", "ldap://localhost")
    rootdn = rootdn or config.get("general", "ldap_rootdn",
                                  "dc=arkos-servers,dc=org")
    conn_type = conn_type or config.get("general", "ldap_conntype", "dynamic")

    if conn_type == "dynamic":
        c = ldap.ldapobject.ReconnectLDAPObject(
            uri, retry_max=3, retry_delay=5.0)
    else:
        c = ldap.initialize(uri)

    try:
        c.simple_bind_s("{0},{1}".format(dn, rootdn), passwd)
    except ldap.INVALID_CREDENTIALS:
        raise Exception("Admin LDAP authentication failed.")
    if dn != "cn=admin":
        data = c.search_s("cn=admins,ou=groups,{0}".format(rootdn),
                          ldap.SCOPE_SUBTREE, "(objectClass=*)",
                          ["member"])[0][1]["member"]
        if "{0},{1}".format(dn, rootdn) not in data:
            raise Exception("User is not an administrator")
    return c


def supervisor_connect():
    """
    Initialize a connection to Supervisor via XML-RPC API.

    :returns: XML-RPC connection object
    """
    s = xmlrpc.client.Server("http://localhost:9001/RPC2")
    return s.supervisor
