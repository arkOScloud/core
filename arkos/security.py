import ConfigParser
import iptc

from arkos import storage, signals
from arkos.system import network
from arkos.utilities import shell, cidr_to_netmask

jailconf = "/etc/fail2ban/jail.conf"
filters = "/etc/fail2ban/filter.d"


def initialize_fw():
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
    # Regenerate our chain.
    # If local ranges are not provided, get them.
    signals.emit("security", "pre_fw_regen")
    flush_fw()
    default_range = range or network.get_active_ranges()
    # For each policy in the system, add a rule
    for x in data:
        range = x.allowed_ranges if hasattr(x, "allowed_ranges") else default_range
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
    rule = iptc.Rule()
    target = iptc.Target(rule, "RETURN")
    rule.target = target
    chain.append_rule(rule)
    save_fw()
    signals.emit("security", "post_fw_regen")

def add_fw(protocol, port, ranges=[]):
    # Add rule for this port
    # If range is not provided, assume "0.0.0.0"
    for range in ranges:
        table = iptc.Table(iptc.Table.FILTER)
        chain = iptc.Chain(table, "arkos-apps")
        if not table.is_chain(chain):
            table.create_chain(chain)
        rule = iptc.Rule()
        rule.protocol = protocol
        if not range in ["", "anywhere", "0.0.0.0"]:
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
    # Remove rule(s) in our chain matching this port
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
    # Returns true if rule is found for this port
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
    # Flush out our chain
    signals.emit("security", "fw_flush")
    table = iptc.Table(iptc.Table.FILTER)
    chain = iptc.Chain(table, "arkos-apps")
    if table.is_chain(chain):
        chain.flush()

def save_fw():
    # Save rules to file loaded on boot
    with open("/etc/iptables/iptables.rules", "w") as f:
        f.write(shell("iptables-save")["stdout"])

def get_jail_config():
    cfg = ConfigParser.RawConfigParser()
    if not cfg.read(jailconf):
        raise Exception("Fail2Ban config not found or not readable")
    return cfg

def enable_jail_def(jailname):
    cfg = get_jail_config()
    cfg.set(jailname, "enabled", "true")
    with open(jailconf, "w") as f:
        cfg.write(f)

def disable_jail_def(jailname):
    cfg = get_jail_config()
    cfg.set(jailname, "enabled", "false")
    with open(jailconf, "w") as f:
        cfg.write(f)

def enable_all_def(obj):
    cfg = get_jail_config()
    for jail in obj["f2b"]:
        cfg.set(jail["id"], "enabled", "true")
    with open(jailconf, "w") as f:
        cfg.write(f)

def disable_all_def(obj):
    cfg = get_jail_config()
    for jail in obj["f2b"]:
        cfg.set(jail["id"], "enabled", "false")
    with open(jailconf, "w") as f:
        cfg.write(f)

def bantime_def(bantime=""):
    cfg = get_jail_config()
    if bantime == "":
        return cfg.get("DEFAULT", "bantime")
    elif bantime != cfg.get("DEFAULT", "bantime"):
        cfg.set("DEFAULT", "bantime", bantime)
        with open(jailconf, "w") as f:
            cfg.write(f)

def findtime_def(findtime=""):
    cfg = get_jail_config()
    if findtime == "":
        return cfg.get("DEFAULT", "findtime")
    elif findtime != cfg.get("DEFAULT", "findtime"):
        cfg.set("DEFAULT", "findtime", findtime)
        with open(jailconf, "w") as f:
            cfg.write(f)

def maxretry_def(maxretry=""):
    cfg = get_jail_config()
    if maxretry == "":
        return cfg.get("DEFAULT", "maxretry")
    elif maxretry != cfg.get("DEFAULT", "maxretry"):
        cfg.set("DEFAULT", "maxretry", maxretry)
        with open(jailconf, "w") as f:
            cfg.write(f)

def ignoreip_def(ranges):
    ranges.insert(0, "127.0.0.1/8")
    s = " ".join(ranges)
    cfg = get_jail_config()
    if s != cfg.get("DEFAULT", "ignoreip"):
        cfg.set("DEFAULT", "ignoreip", s)
        with open(jailconf, "w") as f:
            cfg.write(f)

def get_defense_rules():
    lst = []
    remove = []
    cfg = get_jail_config()
    fcfg = ConfigParser.SafeConfigParser()
    for c in storage.apps.get("applications"):
        if hasattr(c, "f2b") and hasattr(c, "f2b_name"):
            lst.append({"id": c.f2b_name,
                "icon": c.f2b_icon,
                "f2b": c.f2b})
        elif hasattr(c, "f2b"):
            lst.append({"id": c.id,
                "icon": c.icon,
                "f2b": c.f2b})
    for p in lst:
        for l in p["f2b"]:
            if not "custom" in l:
                try:
                    jail_opts = cfg.items(l["id"])
                except ConfigParser.NoSectionError:
                    remove.append(p)
                    continue
                filter_name = cfg.get(l["id"], "filter")
                if "%(__name__)s" in filter_name:
                    filter_name = filter_name.replace("%(__name__)s", l["id"])
                c = fcfg.read([filters+"/common.conf",
                    filters+"/"+filter_name+".conf"])
                filter_opts = fcfg.items("Definition")
                l["jail_opts"] = jail_opts
                l["filter_name"] = filter_name
                l["filter_opts"] = filter_opts
            else:
                if not os.path.exists(filters+"/"+l["filter_name"]+".conf"):
                    fcfg = ConfigParser.SafeConfigParser()
                    fcfg.add_section("Definition")
                    for o in l["filter_opts"]:
                        fcfg.set("Definition", o[0], o[1])
                    with open(filters+"/"+l["filter_name"]+".conf", "w") as f:
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
                    fcfg.read([filters+"/common.conf",
                        filters+"/"+filter_name+".conf"])
                    filter_opts = fcfg.items("Definition")
                    l["jail_opts"] = jail_opts
                    l["filter_name"] = filter_name
                    l["filter_opts"] = filter_opts
    for x in remove:
        lst.remove(x)
    return lst
