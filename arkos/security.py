import ConfigParser
import iptc

from arkos import storage
from arkos.system import network
from arkos.utilities import shell, cidr_to_netmask

jailconf = '/etc/fail2ban/jail.conf'
filters = '/etc/fail2ban/filter.d'


def initialize_fw():
    tb = iptc.Table(iptc.Table.FILTER)
    c = iptc.Chain(tb, 'INPUT')
    c.flush()

    # Accept loopback
    r = iptc.Rule()
    r.in_interface = 'lo'
    t = iptc.Target(r, 'ACCEPT')
    r.target = t
    c.append_rule(r)

    # Accept designated apps
    r = iptc.Rule()
    t = iptc.Target(r, 'arkos-apps')
    r.target = t
    c.append_rule(r)

    # Allow ICMP (ping)
    shell('iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT')

    # Accept established/related connections
    # Unfortunately this has to be done clasically
    shell('iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT')

    # Reject all else by default
    r = iptc.Rule()
    t = iptc.Target(r, 'DROP')
    r.target = t
    c.append_rule(r)
    save_fw()

def regen_fw(data, range=[]):
    # Regenerate our chain.
    # If local ranges are not provided, get them.
    flush_fw()
    range = range or network.get_active_ranges()
    for x in data:
        for p in x.ports:
            if x.policy == 2:
                add_fw(p[0], p[1], ['anywhere'])
            elif x.policy == 1:
                if hasattr(x, "allowed_ranges"):
                    rng = x.allowed_ranges
                else:
                    rng = range
                add_fw(p[0], p[1], rng)
            else:
                remove_fw(p[0], p[1])
    tb = iptc.Table(iptc.Table.FILTER)
    c = iptc.Chain(tb, "arkos-apps")
    r = iptc.Rule()
    t = iptc.Target(r, 'RETURN')
    r.target = t
    c.append_rule(r)

def add_fw(protocol, port, ranges=[]):
    # Add rule for this port
    # If range is not provided, assume '0.0.0.0'
    for x in ranges:
        tb = iptc.Table(iptc.Table.FILTER)
        c = iptc.Chain(tb, "arkos-apps")
        if not tb.is_chain(c):
            tb.create_chain(c)
        r = iptc.Rule()
        r.protocol = protocol
        if not x in ['', 'anywhere', '0.0.0.0']:
            ip, cidr = x.split('/')
            mask = cidr_to_netmask(int(cidr))
            r.src = ip + '/' + mask
        m = iptc.Match(r, protocol)
        m.dport = str(port)
        r.add_match(m)
        t = iptc.Target(r, 'ACCEPT')
        r.target = t
        c.insert_rule(r)

def remove_fw(protocol, port, ranges=[]):
    # Remove rule(s) in our chain matching this port
    # If range is not provided, delete all rules for this port
    for x in ranges:
        tb = iptc.Table(iptc.Table.FILTER)
        c = iptc.Chain(tb, "arkos-apps")
        if not tb.is_chain(c):
            return
        for r in c.rules:
            if range not in ['', "anywhere", "0.0.0.0"]:
                if r.matches[0].dport == port and range in r.dst:
                    c.delete_rule(r)
            else:
                if r.matches[0].dport == port:
                    c.delete_rule(r)

def find_fw(protocol, port, range=""):
    # Returns true if rule is found for this port
    # If range IS provided, return true only if range is the same
    tb = iptc.Table(iptc.Table.FILTER)
    c = iptc.Chain(tb, "arkos-apps")
    if not tb.is_chain(c):
        return False
    for r in c.rules:
        if range:
            if r.matches[0].dport == port and range in r.dst:
                return True
        elif not range and r.matches[0].dport == port:
            return True
    return False

def flush_fw():
    # Flush out our chain
    tb = iptc.Table(iptc.Table.FILTER)
    c = iptc.Chain(tb, "arkos-apps")
    if tb.is_chain(c):
        c.flush()

def save_fw():
    # Save rules to file loaded on boot
    with open('/etc/iptables/iptables.rules', 'w') as f:
        f.write(shell('iptables-save')["stdout"])

def get_jail_config():
    cfg = ConfigParser.RawConfigParser()
    if not cfg.read(jailconf):
        raise Exception("Fail2Ban config not found or not readable")
    return cfg

def enable_jail_def(jailname):
    cfg = get_jail_config()
    cfg.set(jailname, 'enabled', 'true')
    with open(jailconf, 'w') as f:
        cfg.write(f)

def disable_jail_def(jailname):
    cfg = get_jail_config()
    cfg.set(jailname, 'enabled', 'false')
    with open(jailconf, 'w') as f:
        cfg.write(f)

def enable_all_def(obj):
    cfg = get_jail_config()
    for jail in obj['f2b']:
        cfg.set(jail['name'], 'enabled', 'true')
    with open(jailconf, 'w') as f:
        cfg.write(f)

def disable_all_def(obj):
    cfg = get_jail_config()
    for jail in obj['f2b']:
        cfg.set(jail['name'], 'enabled', 'false')
    with open(jailconf, 'w') as f:
        cfg.write(f)

def bantime_def(bantime=''):
    cfg = get_jail_config()
    if bantime == '':
        return cfg.get('DEFAULT', 'bantime')
    elif bantime != cfg.get('DEFAULT', 'bantime'):
        cfg.set('DEFAULT', 'bantime', bantime)
        with open(jailconf, 'w') as f:
            cfg.write(f)

def findtime_def(findtime=''):
    cfg = get_jail_config()
    if findtime == '':
        return cfg.get('DEFAULT', 'findtime')
    elif findtime != cfg.get('DEFAULT', 'findtime'):
        cfg.set('DEFAULT', 'findtime', findtime)
        with open(jailconf, 'w') as f:
            cfg.write(f)

def maxretry_def(maxretry=''):
    cfg = get_jail_config()
    if maxretry == '':
        return cfg.get('DEFAULT', 'maxretry')
    elif maxretry != cfg.get('DEFAULT', 'maxretry'):
        cfg.set('DEFAULT', 'maxretry', maxretry)
        with open(jailconf, 'w') as f:
            cfg.write(f)

def ignoreip_def(ranges):
    ranges.insert(0, '127.0.0.1/8')
    s = ' '.join(ranges)
    cfg = get_jail_config()
    if s != cfg.get('DEFAULT', 'ignoreip'):
        cfg.set('DEFAULT', 'ignoreip', s)
        with open(jailconf, 'w') as f:
            cfg.write(f)

def get_defense_rules():
    lst = []
    remove = []
    cfg = get_jail_config()
    fcfg = ConfigParser.SafeConfigParser()
    for c in storage.apps.get("installed"):
        if hasattr(c, 'f2b') and hasattr(c, 'f2b_name'):
            lst.append({'name': c.f2b_name,
                'icon': c.f2b_icon,
                'f2b': c.f2b})
        elif hasattr(c, 'f2b'):
            lst.append({'name': c.name,
                'icon': c.icon,
                'f2b': c.f2b})
    for p in lst:
        for l in p['f2b']:
            if not 'custom' in l:
                try:
                    jail_opts = cfg.items(l['name'])
                except ConfigParser.NoSectionError:
                    remove.append(p)
                    continue
                filter_name = cfg.get(l['name'], 'filter')
                if "%(__name__)s" in filter_name:
                    filter_name = filter_name.replace("%(__name__)s", l['name'])
                c = fcfg.read([filters+'/common.conf', 
                    filters+'/'+filter_name+'.conf'])
                filter_opts = fcfg.items('Definition')
                l['jail_opts'] = jail_opts
                l['filter_name'] = filter_name
                l['filter_opts'] = filter_opts
            else:
                if not os.path.exists(filters+'/'+l['filter_name']+'.conf'):
                    fcfg = ConfigParser.SafeConfigParser()
                    fcfg.add_section('Definition')
                    for o in l['filter_opts']:
                        fcfg.set('Definition', o[0], o[1])
                    with open(filters+'/'+l['filter_name']+'.conf', 'w') as f:
                        fcfg.write(f)
                if not l['name'] in cfg.sections():
                    cfg.add_section(l['name'])
                    for o in l['jail_opts']:
                        cfg.set(l['name'], o[0], o[1])
                    with open(jailconf, 'w') as f:
                        cfg.write(f)
                else:
                    jail_opts = cfg.items(l['name'])
                    filter_name = cfg.get(l['name'], 'filter')
                    fcfg.read([filters+'/common.conf', 
                        filters+'/'+filter_name+'.conf'])
                    filter_opts = fcfg.items('Definition')
                    l['jail_opts'] = jail_opts
                    l['filter_name'] = filter_name
                    l['filter_opts'] = filter_opts
    for x in remove:
        lst.remove(x)
    return lst
