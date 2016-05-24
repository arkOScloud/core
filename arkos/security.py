import ConfigParser

from arkos import storage, signals
from arkos.system import network
from arkos.utilities import shell, cidr_to_netmask

jailconf = "/etc/fail2ban/jail.conf"
filters = "/etc/fail2ban/filter.d"


def initialize_firewall():
    signals.emit("security", "pre_fw_init")
    flush_chain("INPUT")

    # Accept loopback
    shell("iptables -A INPUT -i lo -j ACCEPT")

    # Accept designated apps
    shell("iptables -N arkos-apps")
    shell("iptables -A INPUT -j arkos-apps")

    # Allow ICMP (ping)
    shell("iptables -A INPUT -p icmp -m icmp --icmp-type echo-request -j ACCEPT")

    # Accept established/related connections
    shell("iptables -A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT")

    # Reject all else by default
    shell("iptables -A INPUT -j DROP")

    save_rules()
    signals.emit("security", "post_fw_init")

def regenerate_firewall(data, range=[]):
    # Regenerate our chain.
    # If local ranges are not provided, get them.
    signals.emit("security", "pre_fw_regen")
    flush_chain("arkos-apps")
    default_range = range or network.get_active_ranges()
    # For each policy in the system, add a rule
    for x in data:
        range = getattr(x, "allowed_ranges", default_range)
        for port in x.ports:
            if x.policy == 2:
                add_rule("ACCEPT", port[0], port[1], ["anywhere"])
            elif x.policy == 1:
                add_rule("ACCEPT", port[0], port[1], range)
            else:
                add_rule("REJECT", port[0], port[1])
    shell("iptables -A arkos-apps -j RETURN")
    save_rules()
    signals.emit("security", "post_fw_regen")

def add_rule(opt, protocol, port, ranges=[]):
    # Add rule for this port
    # If range is not provided, assume "0.0.0.0"
    cmd = "iptables -I arkos-apps {src} -p {ptc} -m {ptc} --dport {prt} -j {opt}"
    src = ""
    for x in [r for r in ranges if r not in ["", "anywhere", "0.0.0.0"]]:
        src = "-s " if not src else (src + ",")
        ip, cidr = x.split("/")
        mask = cidr_to_netmask(int(cidr))
        src += ip + "/" + mask
    s = shell(cmd.format(src=src, ptc=protocol, prt=port, opt=opt))
    if s["code"] != 0 and "No chain/target/match by that name" in s["stderr"]:
        # Create chain if not exists
        shell("iptables -N arkos-apps")
        shell(cmd.format(src=src, ptc=protocol, prt=port, opt=opt))

def flush_chain(chain):
    # Flush out our chain
    signals.emit("security", "fw_flush")
    shell("iptables -F {0}".format(chain))

def save_rules():
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
