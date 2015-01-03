import time

from arkos.core import Framework
from arkos.core.utilities import api, shell, random_string


class Updates(Framework):
    REQUIRES = []
    
    def on_start(self):
        if self.app.conf.get("updates", "check_updates", True):
            try:
                self.check_updates()
            except Exception, e:
                self.app.storage.put("messages", {"id": random_string()[0:8], "class": "error", 
                    "finished": True,"message": "Initial update check failed. See log for details"})
                self.app.logger.error("Initial update check failed: %s" % str(e))
            if not "updates" in [x["unit"] for x in self.app.storage.get_list("scheduled")]:
                op = {"id": random_string()[0:8], "unit": "updates", 
                    "order": "check_updates", "data": {}, "reschedule": 43200}
                self.app.storage.redis.zadd("arkos:scheduled", int(time.time())+43200, op)
    
    def check_updates(self):
        server = self.app.conf.get("general", "repo_server")
        current = self.app.conf.get("updates", "current_update", 0)
        data = api("https:/%s/updates/%s/" % (server, current), crit=True)
        current_list = sorted([x["id"] for x in self.app.storage.get_list("updates")])
        for x in data:
            if not x["id"] in current_list:
                self.app.storage.append("updates", x)
    
    def install_updates(self):
        updates = self.app.storage.get_list("updates")
        if not updates:
            return
        id = random_string()[0:8]
        amount = len(updates)
        fail = False
        for x in enumerate(updates):
            self.app.storage.append("messages", {"id": id, "class": "info", "block": True,
                "message": "Installing update %s of %s..." % (x[0], amount)})
            for y in enumerate(x[1]["operations"]):
                if y[1]["unit"] == "shell":
                    s = shell(y[1]["order"], stdin=y[1]["data"])
                    if s["code"] != 0:
                        fail = {"step": y[0], "result": s["stderr"]}
                        break
                elif y["unit"] == "fetch":
                    try:
                        download(y[1]["order"], y[1]["data"], True)
                    except Exception, e:
                        code = 1
                        if hasattr(e, "code"):
                            code = e.code
                        fail = {"step": y[0], "result": code}
                        break
                else:
                    func = getattr(self.app.manager.components[y[1]["unit"]], y[1]["order"])
                    try:
                        response = func(**y[1]["data"])
                    except Exception, e:
                        fail = {"step": y[0], "result": s["stderr"]}
                        break
            else:
                self.app.conf.set("updates", "current_update", x[1]["id"])
                self.app.storage.remove("updates", x[1])
            if fail:
                self.app.storage.append("messages", {"id": id, "finished": True, "block": False,
                    "class": "error", "message": "Installation of update #%s failed. See logs for details." % x[1]["id"]})
                break
        else:
            self.app.storage.append("messages", {"id": id, "finished": True, "block": False,
                "class": "success", "message": "%s update%s installed successfully. Please restart your system." \
                % (amount, "" if amount == 1 else "s")})
