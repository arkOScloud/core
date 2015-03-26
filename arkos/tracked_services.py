import json
import os
import random
import sys

from arkos import config, storage, security

COMMON_PORTS = [3000, 3306, 5222, 5223, 5232, 8000, 8080]

if os.path.exists(os.path.join(sys.path[0], "policies.json")):
    policy_path = os.path.join(sys.path[0], "policies.json")
elif os.path.exists("/etc/arkos/policies.json"):
    policy_path = "/etc/arkos/policies.json"


class SecurityPolicy:
    def __init__(self, type="", id="", name="", icon="", ports=[], policy=2):
        self.type = type
        self.id = id
        self.name = name
        self.icon = icon
        self.ports = ports
        self.policy = policy

    def save(self, fw=True):
        with open(policy_path, "r") as f:
            policies = json.loads(f.read())
        if policies.has_key(self.type):
            policies[self.type][self.id] = self.policy
        else:
            policies[self.type] = {}
            policies[self.type][self.id] = self.policy
        with open(policy_path, "w") as f:
            f.write(json.dumps(policies, sort_keys=True, 
                indent=4, separators=(',', ': ')))
        if config.get("general", "firewall", True) and fw:
            security.regen_fw(get())
        if not storage.policies.get("policies", self.id):
            storage.policies.add("policies", self)

    def remove(self, fw=True):
        with open(policy_path, "r") as f:
            policies = json.loads(f.read())
        if policies.has_key(self.type) and len(policies[self.type]) <= 1:
            del policies[self.type]
        elif policies.has_key(self.type) and policies[self.type].has_key(self.id):
            del policies[self.type][self.id]
        with open(policy_path, "w") as f:
            f.write(json.dumps(policies, sort_keys=True, 
                indent=4, separators=(',', ': ')))
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
    with open(policy_path, "r") as f:
        policies = json.loads(f.read())
    if not policy:
        if policies.has_key(type) and policies[type].has_key(id):
            policy = policies[type][id]
        else:
            policy = 2
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
    with open(policy_path, "r") as f:
        policies = json.loads(f.read())
    svcs = get()
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
    with open(policy_path, "w") as f:
        f.write(json.dumps(newpolicies, sort_keys=True, 
            indent=4, separators=(',', ': ')))

def get_open_port(ignore_common=False):
    data = get()
    ports = [[y[1] for y in x.ports] for x in data]
    if not ignore_common: ports = ports + COMMON_PORTS
    r = random.randint(1025, 65534)
    return r if not r in ports else get_open_port()

def initialize():
    with open(policy_path, "r") as f:
        policies = json.loads(f.read())
    policy = policies["arkos"]["arkos"] if policies.has_key("arkos") \
        and policies["arkos"].has_key("arkos") else 2
    storage.policies.add("policies", SecurityPolicy("arkos", "arkos", 
        "System Management (Genesis/APIs)", "gen-arkos-round", 
        [("tcp", int(config.get("genesis", "port"))), ("tcp", 8765)], policy))
    if policies.has_key("custom"):
        for x in policies["custom"]:
            storage.policies.add("policies", SecurityPolicy("custom", x["id"], 
                x["name"], x["icon"], x["ports"], x["policy"]))
