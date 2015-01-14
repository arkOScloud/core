import json
import os
import random
import sys

from arkos import config, applications, websites, security

COMMON_PORTS = [3000, 3306, 5222, 5223, 5232, 8000, 8080, 8765]


class SecurityPolicy:
    def __init__(self, type="", id="", name="", icon="", ports=[], policy=2)
        self.type = type
        self.id = id
        self.name = name
        self.icon = icon
        self.ports = ports
        self.policy = policy
    
    def save(self, fw=True):
        with open(config.get("general", "policy_path"), "r") as f:
            policies = json.loads(f.read())
        if policies.has_key(self.type):
            policies[self.type][self.id] = policy
        else:
            policies[self.type] = {}
            policies[self.type][self.id] = policy
        with open(config.get("general", "policy_path"), "w") as f:
            f.write(json.dumps(policies, sort_keys=True, 
                indent=4, separators=(',', ': ')))
        if config.get("general", "firewall", True) and fw:
            security.regen_fw(get(policies=policies))
    
    def remove(self, fw=True):
        with open(config.get("general", "policy_path"), "r") as f:
            policies = json.loads(f.read())
        if policies.has_key(self.type) and len(policies[self.type]) <= 1:
            del policies[self.type]
        elif policies.has_key(self.type) and policies[self.type].has_key(self.id):
            del policies[self.type][self.id]
        with open(config.get("general", "policy_path"), "w") as f:
            f.write(json.dumps(policies, sort_keys=True, 
                indent=4, separators=(',', ': ')))
        if config.get("general", "firewall", True) and fw:
            security.regen_fw(get(policies=policies))


def get(type=None, policies={}):
    data = storage.policies.get("policies")
    if not data:
        data = scan(policies)
    if type:
        tlist = []
        for x in data:
            if x == type:
                tlist.append(data[x])
        if tlist:
            return tlist
        return None
    return data

def scan(policies={}):
    # Get policies
    if not policies:
        with open(config.get("general", "policy_path"), "r") as f:
            policies = json.loads(f.read())
    # Get services
    services = []
    policy = policies["arkos"]["kraken"] if policies.has_key("arkos") \
        and policies["arkos"].has_key("arkos") else 2
    services.append(SecurityPolicy("arkos", "arkos", "System Management (Genesis/APIs)",
        "gen-arkos-round", [("tcp", int(config.get("genesis", "port"))), ("tcp", 8765)], policy))
    if policies.has_key("custom"):
        for x in policies["custom"]:
            services.append(SecurityPolicy("custom", x["id"], x["name"], x["icon"], x["ports"], x["policy"]))
    for p in applications.get():
        for s in p.services:
            policy = policies[p.id][s["binary"]] if policies.has_key(p.id) \
                and policies[p.id].has_key(s["binary"]) else 2
            services.append(SecurityPolicy(p.id, s["binary"], s["name"], p.icon,
                s["ports"], policy))
    for s in websites.get():
        policy = policies[s.meta.id][s.name] if policies.has_key(s.meta.id) \
            and policies[s.meta.id].has_key(s.name) else 2
        services.append(SecurityPolicy(s.meta.id, s.name, s.name, s.icon,
            [("tcp", s.port)], policy))
    storage.policies.set("policies", services)
    return services

def refresh_policies():
    with open(config.get("general", "policy_path"), "r") as f:
        policies = json.loads(f.read())
    svcs = scan(policies=policies)
    newpolicies = {}
    for x in policies:
        if x == "custom":
            newpolicies["custom"] = policies["custom"]
        for y in svcs:
            if x == y.type:
                if not x in newpolicies:
                    newpolicies[x] = {}
                for s in policies[x]:
                    if s == y.id:
                        newpolicies[x][s] = policies[x][s]
    with open(config.get("general", "policy_path"), "w") as f:
        f.write(json.dumps(newpolicies, sort_keys=True, 
            indent=4, separators=(',', ': ')))

def get_open_port(ignore_common=False):
    data = get()
    ports = [[y[1] for y in x.ports] for x in data]
    if not ignore_common: ports = ports + COMMON_PORTS
    r = random.randint(1025, 65534)
    return r if not r in ports else get_open_port()
