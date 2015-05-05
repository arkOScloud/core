import os
import random
import sys

from arkos import config, policies, signals, storage, security

COMMON_PORTS = [3000, 3306, 5222, 5223, 5232, 8000, 8080]


class SecurityPolicy:
    def __init__(self, type="", id="", name="", icon="", ports=[], policy=2):
        self.type = type
        self.id = id
        self.name = name
        self.icon = icon
        self.ports = ports
        self.policy = policy

    def save(self, fw=True):
        policies.set(self.type, self.id, self.policy)
        policies.save()
        if config.get("general", "firewall", True) and fw:
            security.regen_fw(get())
        if not storage.policies.get("policies", self.id):
            storage.policies.add("policies", self)

    def remove(self, fw=True):
        policies.remove(self.type, self.id)
        policies.save()
        if config.get("general", "firewall", True) and fw:
            security.regen_fw(get())
        storage.policies.remove("policies", self)

    def as_dict(self):
        return {
            "type": self.type,
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "ports": self.ports,
            "policy": self.policy,
            "is_ready": True
        }


def get(id=None, type=None):
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

def register(type, id, name, icon, ports, policy=0, fw=True):
    if not policy:
        policy = policies.get(type, id, 2)
    pget = get(type=type)
    if pget:
        for x in pget:
            if x.id == id:
                storage.policies.remove("policies", x)
    svc = SecurityPolicy(type, id, name, icon, ports, policy)
    svc.save(fw)

def deregister(type, id="", fw=True):
    for x in get(type=type):
        if not id:
            x.remove(fw=False)
        elif x.id == id:
            x.remove(fw=False)
            break
    if config.get("general", "firewall", True) and fw:
        security.regen_fw(get())

def refresh_policies():
    svcs = get()
    newpolicies = {}
    for x in policies.get_all():
        if x == "custom":
            newpolicies["custom"] = policies.get_all("custom")
        for y in svcs:
            if x == y.type:
                if not x in newpolicies:
                    newpolicies[x] = {}
                for s in policies.get_all(x):
                    if s == y.id:
                        newpolicies[x][s] = policies.get(x, s)
    policies.config = newpolicies
    policies.save()

def is_open_port(port, ignore_common=False):
    data = get()
    ports = []
    for x in data:
        for y in x.ports:
            ports.append(int(y[1]))
    if not ignore_common: ports = ports + COMMON_PORTS
    return port not in ports

def get_open_port(ignore_common=False):
    data = get()
    ports = []
    for x in data:
        for y in x.ports:
            ports.append(int(y[1]))
    if not ignore_common: ports = ports + COMMON_PORTS
    r = random.randint(8001, 65534)
    return r if not r in ports else get_open_port()

def initialize():
    policy = policies.get("arkos", "arkos", 2)
    storage.policies.add("policies", SecurityPolicy("arkos", "arkos",
        "System Management (Genesis/APIs)", "fa fa-desktop",
        [("tcp", int(config.get("genesis", "port")))], policy))
    for x in policies.get_all("custom"):
        storage.policies.add("policies", SecurityPolicy("custom", x["id"],
            x["name"], x["icon"], x["ports"], x["policy"]))

def register_website(site):
    register(site.meta.id if site.meta else "website", site.id,
        site.name if hasattr(site, "name") and site.name else site.id,
        site.meta.icon if site.meta else "fa fa-globe", [("tcp", site.port)])

def deregister_website(site):
    deregister(site.meta.id if site.meta else "website", site.id)

signals.add("tracked_services", "websites", "site_loaded", register_website)
signals.add("tracked_services", "websites", "site_installed", register_website)
signals.add("tracked_services", "websites", "site_removed", deregister_website)
