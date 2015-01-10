import json
import os
import random
import sys

from arkos import storage, security
from arkos.utilities import dictfilter

COMMON_PORTS = [3000, 3306, 5222, 5223, 8000, 8080, 8765]


def get(policies={}):
    # Get policies
    if not policies:
        with open(config.get("general", "policy_path"), "r") as f:
            policies = json.loads(f.read())
    # Get services
    services = {}
    policy = policies["arkos"]["genesis"] if policies.has_key("arkos") \
        and policies["arkos"].has_key("genesis") else 2
    services["arkos"]["genesis"] = {"policy": policy, 
        "name": "System Management (Genesis/APIs)", "icon": "gen-arkos-round", 
        "ports": [("tcp", int(config.get("genesis", "port"))), ("tcp", 8765)]}
    for p in storage.apps.get("installed")
        for s in p.services:
            policy = policies[p.id][s["binary"]] if policies.has_key(p.id) \
                and policies[p.id].has_key(s["binary"]) else 2
            if not services.has_key(p.id): services[p.id] = {}
            services[p.id][s['binary']] = {"name": s['name'], 
                "icon": p.icon, "ports": s['ports'], "policy": policy}
    for s in storage.sites.get("sites"):
        policy = policies[s.meta.id][s.name] if policies.has_key(s.meta.id) \
            and policies[s.meta.id].has_key(s.name) else 2
        if not services.has_key(s.meta.id): services[s.meta.id] = {}
        services[s.meta.id][s.name] = {"name": s.name, "icon": s.icon, 
            "ports": [('tcp', s.port)], "policy": policy}
    return services

def update_policy(pid, sid, policy, fw=True):
    with open(config.get("general", "policy_path"), "r") as f:
        policies = json.loads(f.read())
    if policies.has_key(pid):
        policies[pid][sid] = policy
    else:
        policies[pid] = {}
        policies[pid][sid] = policy
    with open(config.get("general", "policy_path"), "w") as f:
        f.write(json.dumps(policies, sort_keys=True, 
            indent=4, separators=(',', ': ')))
    if config.get("general", "firewall", True) and fw:
        security.regen_fw(get(policies))

def remove_policy(pid, sid="", fw=True):
    with open(config.get("general", "policy_path"), "r") as f:
        policies = json.loads(f.read())
    if policies.has_key(pid) and not sid:
        del policies[pid]
    elif policies.has_key(pid) and policies[pid].has_key(sid):
        del policies[pid][sid]
    with open(config.get("general", "policy_path"), "w") as f:
        f.write(json.dumps(policies, sort_keys=True, 
            indent=4, separators=(',', ': ')))
    if config.get("general", "firewall", True) and fw:
        security.regen_fw(get(policies))

def refresh_policies():
    with open(config.get("general", "policy_path"), "r") as f:
        policies = json.loads(f.read())
    svcs = get()
    newpolicies = {}
    for x in policies:
        if x == "custom":
            newpolicies["custom"] = policies["custom"]
        if x in svcs:
            newpolicies[x] = {}
            for s in policies[x]:
                if s in svcs[x]:
                    newpolicies[x][s] = policies[x][s]
    with open(config.get("general", "policy_path"), "w") as f:
        f.write(json.dumps(newpolicies, sort_keys=True, 
            indent=4, separators=(',', ': ')))

def get_open_port(ignore_common=False):
    data = get()
    ports = [[[z[1] for z in y["ports"]] for y in data[x]] for x in data]
    if not ignore_common: ports = ports + COMMON_PORTS
    r = random.randint(1025, 65534)
    return r if not r in ports else get_open_port()
