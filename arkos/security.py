"""
Functions for managing iptables firewall and fail2ban defence security.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import configparser
import iptc
import os

from arkos import storage, signals
from arkos.system import network
from arkos.utilities import shell, cidr_to_netmask

jailconf = "/etc/fail2ban/jail.conf"
filters = "/etc/fail2ban/filter.d"


def initialize_fw():
    """Flush all iptables rules and setup a new clean arkOS firewall chain."""
    signals.emit("security", "pre_fw_init")
    table = iptc.Table(iptc.Table.FILTER)
    chain = iptc.Chain(table, "INPUT")
    chain.flush()

    # Accept loopback
    rule = iptc.Rule()
    rule.in_interface = "lo"
    target = iptc.Target(rule, "ACCEPT")
    rule.target = target
    chain.append_rule(rule)

    # Accept designated apps
    app_chain = iptc.Chain(table, "arkos-apps")
    if not table.is_chain(app_chain):
        table.create_chain(app_chain)
    rule = iptc.Rule()
    target = iptc.Target(rule, "arkos-apps")
    rule.target = target
    chain.append_rule(rule)

    # Allow ICMP (ping)
    rule = iptc.Rule()
    rule.protocol = "icmp"
    target = iptc.Target(rule, "ACCEPT")
    rule.target = target
    match = iptc.Match(rule, "icmp")
    match.icmp_type = "echo-request"
    chain.append_rule(rule)

    # Accept established/related connections
    rule = iptc.Rule()
    target = iptc.Target(rule, "ACCEPT")
    rule.target = target
    match = iptc.Match(rule, "conntrack")
    match.ctstate = "ESTABLISHED,RELATED"
    chain.append_rule(rule)

    # Reject all else by default
    rule = iptc.Rule()
    target = iptc.Target(rule, "DROP")
    rule.target = target
    chain.append_rule(rule)
    save_fw()
    signals.emit("security", "post_fw_init")


def regen_fw(data, range=[]):
    """
    Flush and regenerate arkOS firewall chain.

    If ``range`` is not specified, network module will guess what they are.

    :param SecurityPolicy data: Security policies to enact
    :param list range: Range(s) of local network(s) ('192.168.0.0/24')
    """
    signals.emit("security", "pre_fw_regen")
    flush_fw()
    # If local ranges are not provided, get them.
    default_range = range or network.get_active_ranges()
    # For each policy in the system, add a rule
    for x in data:
        range = getattr(x, "allowed_ranges", default_range)
        for port in x.ports:
            if x.policy == 2:
                add_fw(port[0], port[1], ["anywhere"])
            elif x.policy == 1:
                add_fw(port[0], port[1], range)
            else:
                remove_fw(port[0], port[1])
    # Create our app chain
    table = iptc.Table(iptc.Table.FILTER)
    chain = iptc.Chain(table, "arkos-apps")
    if not table.is_chain(chain):
        table.create_chain(chain)
    rule = iptc.Rule()
    target = iptc.Target(rule, "RETURN")
    rule.target = target
    chain.append_rule(rule)
    save_fw()
    signals.emit("security", "post_fw_regen")


def add_fw(protocol, port, ranges=[]):
    """
    Allow firewall access for specified service.

    If ``ranges`` is not specified, defaults to open access to all hosts.

    :param str protocol: either "TCP" or "UDP"
    :param int port: Port number of service
    :param list ranges: Range(s) of local network(s) ('192.168.0.0/24')
    """
    # If range is not provided, assume "0.0.0.0"
    for range in ranges:
        table = iptc.Table(iptc.Table.FILTER)
        chain = iptc.Chain(table, "arkos-apps")
        if not table.is_chain(chain):
            table.create_chain(chain)
        rule = iptc.Rule()
        rule.protocol = protocol
        if range not in ["", "anywhere", "0.0.0.0"]:
            ip, cidr = range.split("/")
            mask = cidr_to_netmask(int(cidr))
            rule.src = ip + "/" + mask
        match = iptc.Match(rule, protocol)
        match.dport = str(port)
        rule.add_match(match)
        target = iptc.Target(rule, "ACCEPT")
        rule.target = target
        chain.insert_rule(rule)


def remove_fw(protocol, port, ranges=[]):
    """
    Remove firewall rule for specified service.

    :param str protocol: either "TCP" or "UDP"
    :param int port: Port number of service
    :param list ranges: Range(s) of network(s) to remove ('192.168.0.0/24')
    """
    # If range is not provided, delete all rules for this port
    for range in ranges:
        table = iptc.Table(iptc.Table.FILTER)
        chain = iptc.Chain(table, "arkos-apps")
        if not table.is_chain(chain):
            return
        for rule in chain.rules:
            if range not in ["", "anywhere", "0.0.0.0"]:
                if rule.matches[0].dport == port and range in rule.dst:
                    chain.delete_rule(rule)
            else:
                if rule.matches[0].dport == port:
                    chain.delete_rule(rule)


def find_fw(protocol, port, range=""):
    """
    Determine if the rule is already present.

    :param str protocol: either "TCP" or "UDP"
    :param int port: Port number of service
    :param str range: Range of network to check for ('192.168.0.0/24')
    """
    # If range IS provided, return true only if range is the same
    table = iptc.Table(iptc.Table.FILTER)
    chain = iptc.Chain(table, "arkos-apps")
    if not table.is_chain(chain):
        return False
    for rule in chain.rules:
        if range:
            if rule.matches[0].dport == port and range in rule.dst:
                return True
        elif not range and rule.matches[0].dport == port:
            return True
    return False


def flush_fw():
    """Flush the firewall chain."""
    signals.emit("security", "fw_flush")
    table = iptc.Table(iptc.Table.FILTER)
    chain = iptc.Chain(table, "arkos-apps")
    if table.is_chain(chain):
        chain.flush()


def save_fw():
    """Persist firewall rules to a file loadable on boot."""
    with open("/etc/iptables/iptables.rules", "w") as f:
        f.write(shell("iptables-save")["stdout"])


def get_jail_config(jcfg=""):
    """
    Load fail2ban firewall jail configuration from file.

    :param str jailconf: path to jail configuration file
    :returns: jail config
    :rtype: configparser.RawConfigParser
    """
    cfg = configparser.RawConfigParser()
    if not cfg.read(jcfg or jailconf):
        raise Exception("Fail2Ban config not found or not readable")
    return cfg


def enable_jail_def(jailname):
    """
    Enable a fail2ban jail definition.

    :param str jailname: name of jail to enable
    """
    jcfg = os.path.join("/etc/fail2ban/jail.d/{0}.conf".format(jailname))
    if not os.path.exists(jcfg):
        jcfg = jailconf
    cfg = get_jail_config(jcfg)
    cfg.set(jailname, "enabled", "true")
    with open(jcfg, "w") as f:
        cfg.write(f)


def disable_jail_def(jailname):
    """
    Disable a fail2ban jail definition.

    :param str jailname: name of jail to disable
    """
    jcfg = os.path.join("/etc/fail2ban/jail.d/{0}.conf".format(jailname))
    if not os.path.exists(jcfg):
        jcfg = jailconf
    cfg = get_jail_config(jcfg)
    cfg.set(jailname, "enabled", "false")
    with open(jcfg, "w") as f:
        cfg.write(f)


def enable_all_def(service):
    """
    Enable all fail2ban jail definitions for a given service.

    :param dict service: Application service object
    """
    for jail in service["f2b"]:
        enable_jail_def(jail["id"])


def disable_all_def(service):
    """
    Disable all fail2ban jail definitions for a given service.

    :param dict service: Application service object
    """
    for jail in service["f2b"]:
        disable_jail_def(jail["id"])


def bantime_def(bantime=""):
    """
    Get or set default ban time for fail2ban restriction.

    :param str bantime: Time (in seconds) for ban
    :returns: ban time
    :rtype: str
    """
    jailconf = "/etc/fail2ban/jail.conf"
    cfg = get_jail_config(jailconf)
    if bantime == "":
        return cfg.get("DEFAULT", "bantime")
    elif bantime != cfg.get("DEFAULT", "bantime"):
        cfg.set("DEFAULT", "bantime", bantime)
        with open(jailconf, "w") as f:
            cfg.write(f)
        return bantime


def findtime_def(findtime=""):
    """
    Get or set default find time for fail2ban monitoring.

    :param str findtime: Time (in seconds) for find
    :returns: find time
    :rtype: str
    """
    jailconf = "/etc/fail2ban/jail.conf"
    cfg = get_jail_config(jailconf)
    if findtime == "":
        return cfg.get("DEFAULT", "findtime")
    elif findtime != cfg.get("DEFAULT", "findtime"):
        cfg.set("DEFAULT", "findtime", findtime)
        with open(jailconf, "w") as f:
            cfg.write(f)
        return findtime


def maxretry_def(maxretry=""):
    """
    Get or set default max retry time for fail2ban monitoring.

    :param str findtime: Time (in seconds) for max retry
    :returns: max retry time
    :rtype: str
    """
    jailconf = "/etc/fail2ban/jail.conf"
    cfg = get_jail_config(jailconf)
    if maxretry == "":
        return cfg.get("DEFAULT", "maxretry")
    elif maxretry != cfg.get("DEFAULT", "maxretry"):
        cfg.set("DEFAULT", "maxretry", maxretry)
        with open(jailconf, "w") as f:
            cfg.write(f)
        return maxretry


def ignoreip_def(ranges):
    """
    Get or set default IP ranges for fail2ban to ignore.

    :param list ranges: IP address ranges to ignore ('192.168.0.0/24')
    """
    ranges.insert(0, "127.0.0.1/8")
    s = " ".join(ranges)
    cfg = get_jail_config(jailconf)
    if s != cfg.get("DEFAULT", "ignoreip"):
        cfg.set("DEFAULT", "ignoreip", s)
        with open(jailconf, "w") as f:
            cfg.write(f)


def get_defense_rules():
    """Get all defense rules from arkOS service objects."""
    lst = []
    remove = []
    cfg = get_jail_config(jailconf)
    fcfg = configparser.SafeConfigParser()
    for c in storage.apps.get("applications"):
        if hasattr(c, "f2b") and hasattr(c, "f2b_name"):
            lst.append({"id": c.f2b_name, "icon": c.f2b_icon, "f2b": c.f2b})
        elif hasattr(c, "f2b"):
            lst.append({"id": c.id, "icon": c.icon, "f2b": c.f2b})
    for p in lst:
        for l in p["f2b"]:
            if "custom" not in l:
                try:
                    jail_opts = cfg.items(l["id"])
                except configparser.NoSectionError:
                    remove.append(p)
                    continue
                filter_name = cfg.get(l["id"], "filter")
                if "%(__name__)s" in filter_name:
                    filter_name = filter_name.replace("%(__name__)s", l["id"])
                c = fcfg.read(["{0}/common.conf".format(filters),
                               "{0}/{1}.conf".format(filters, filter_name)])
                filter_opts = fcfg.items("Definition")
                l["jail_opts"] = jail_opts
                l["filter_name"] = filter_name
                l["filter_opts"] = filter_opts
            else:
                conf_name = "{0}/{1}.conf".format(filters, l["filter_name"])
                if not os.path.exists(conf_name):
                    fcfg = configparser.SafeConfigParser()
                    fcfg.add_section("Definition")
                    for o in l["filter_opts"]:
                        fcfg.set("Definition", o[0], o[1])
                    with open(conf_name, "w") as f:
                        fcfg.write(f)
                if not l["id"] in cfg.sections():
                    cfg.add_section(l["id"])
                    for o in l["jail_opts"]:
                        cfg.set(l["id"], o[0], o[1])
                    with open(jailconf, "w") as f:
                        cfg.write(f)
                else:
                    jail_opts = cfg.items(l["id"])
                    filter_name = cfg.get(l["id"], "filter")
                    fcfg.read(["{0}/common.conf".format(filters),
                               "{0}/{1}.conf".format(filters, filter_name)])
                    filter_opts = fcfg.items("Definition")
                    l["jail_opts"] = jail_opts
                    l["filter_name"] = filter_name
                    l["filter_opts"] = filter_opts
    for x in remove:
        lst.remove(x)
    return lst
