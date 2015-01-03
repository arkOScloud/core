import json
import os
import random
import sys

from arkos.core.frameworks import Framework
from arkos.core.utilities import dictfilter


COMMON_PORTS = [3000, 3306, 5222, 5223, 8000, 8080]

class TrackedServices(Framework):
    REQUIRES = ["apps", "sites", "security"]

    def on_init(self, policy_path="", firewall=None):
        if not policy_path and firewall == None and not self.app.conf:
            raise Exception("No configuration values passed")
        elif not policy_path:
            if os.path.isfile(os.path.join(sys.path[0], 'policies.json')):
                policy_path = os.path.join(sys.path[0], 'policies.json')
        self.policy_path = policy_path or self.app.conf.get("general", "policy_path")
        self.firewall = firewall or self.app.conf.get("general", "firewall", True)
        if not os.path.exists(self.policy_path):
            with open(self.policy_path, "w") as f:
                f.write("")

    def get(self):
        svrs = []
        if self.app.storage:
            svrs = self.app.storage.get_list("services")
        if not self.app.storage or not sites:
            svrs = self.scan()
        if self.app.storage:
            self.app.storage.append_all("services", svrs)
        return dictfilter(sites, kwargs)

    def scan(self):
        # Get policies
        with open(self.policy_path, "r") as f:
            policies = json.loads(f.read())
        # Get services
        services = []
        policy = policies["arkos"]["fail2ban"] if policies.has_key("arkos") \
            and policies["arkos"].has_key("fail2ban") else {}
        services.append({"type": "internal", "pid": "arkos", 
            "sid": "fail2ban", "name": "Intrusion Prevention", 
            "icon": "gen-arkos-round", "ports": [], "policy": policy})
        for p in self.apps.get():
            if p.has_key('services') and p["pid"] not in [x["pid"] for x in servers]:
                for s in p["services"]:
                    policy = policies[p["pid"]][s["binary"]] if policies.has_key(p["pid"]) \
                        and policies[p["pid"]].has_key(s["binary"]) else {}
                    services.append({"type": p["type"], "pid": p["pid"], 
                        "sid": s['binary'], "name": s['name'], 
                        "icon": p["icon"], "ports": s['ports'], 
                        "policy": policy})
        for s in self.sites.get():
            policy = policies[s["type"]][s["name"]] if policies.has_key(s["type"]) \
                and policies[s["type"]].has_key(s["name"]) else {}
            services.append({"type": "website", "pid": s["type"], 
                "sid": s["name"], "name": s["name"], "icon": s["icon"], 
                "ports": [('tcp', s["port"])], "policy": policy})
        return services

    def add(self, stype, pid, sid, name, icon="", ports=[], policy={}):
        s = {"type": stype, "pid": pid, "sid": sid, "name": name, 
            "icon": icon, "ports": ports, "policy": policy}
        if self.app.storage:
            self.app.storage.append("services", s)

    def update(self, old_sid, new_sid, name, icon="", ports=[]):
        s = self.get(sid=old_sid)
        self.remove(s)
        self.add(s["type"], s["pid"], new_sid, name, icon, ports, s["policy"])
        if self.firewall:
            self.security.regen_fw()

    def update_policy(self, sid, policy):
        s = self.get(sid=sid)
        self.remove(s)
        self.add(s["type"], s["pid"], s["sid"], s["name"], s["icon"], 
            s["ports"], policy)
        with open(self.policy_path, "r") as f:
            policies = json.loads(f.read())
        if policies.has_key(s["pid"]) and policies[s["pid"]].has_key(s["sid"]):
            policies[s["pid"]][s["sid"]] = policy
            with open(self.policy_path, "w") as f:
                f.write(json.dumps(policies, sort_keys=True, 
                    indent=4, separators=(',', ': ')))
        if self.firewall:
            self.security.regen_fw()

    def cleanup_policies(self):
        with open(self.policy_path, "r") as f:
            policies = json.loads(f.read())
        svcs = self.get()
        for x in policies:
            if x == "custom":
                continue
            for s in x:
                if not self.get(pid=x, sid=s):
                    del policies[x][s]
        with open(self.policy_path, "w") as f:
            f.write(json.dumps(policies, sort_keys=True, 
                indent=4, separators=(',', ': ')))

    def remove(self, svc):
        if self.app.storage:
            self.app.storage.remove("services", svc)
        if self.firewall:
            self.security.regen_fw()

    def remove_by_pid(self, pid):
        for x in self.get(pid=pid):
            self.remove(x)

    def get_open_port(self, ignore_common=False):
        ports = [[x[1] for x in s["ports"]] for s in self.get()]
        if not ignore_common: ports = ports + COMMON_PORTS
        r = random.randint(1025, 65534)
        return r if not r in ports else self.get_open_port()
