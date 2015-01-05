from arkos.core.frameworks import Framework
from arkos.core.utilities import api


class Updates(Framework):
    REQUIRES = []
    
    def on_start(self):
        if self.app.conf.get("updates", "check_updates", True):
            try:
                self.check_updates()
            except Exception, e:
                self.app.ops.put_message("error", "Initial update check failed. See log for details", finished=True)
                self.app.logger.error("Initial update check failed: %s" % str(e))
                task = self.app.ops.form_task(tasks=[[0, {"unit": "updates", "order": "check_updates"}]])
                self.app.ops.schedule_task(task, 43200.0, 43200.0)
    
    def check_updates(self, **kwargs):
        server = self.app.conf.get("general", "repo_server")
        current = self.app.conf.get("updates", "current_update", 0)
        data = api("https://%s/updates/%s" % (server, current), crit=True)
        self.app.storage.delete("updates")
        pipe = self.app.storage.pipeline()
        for x in data:
            self.app.storage.append("updates", x, pipe=pipe)
        self.app.storage.execute(pipe)
    
    def install_updates(self):
        updates = self.app.storage.get_list("updates")
        if not updates:
            return
        self.app.storage.delete("updates")
        amount = len(updates)
        for x in enumerate(updates):
            x[1]["operations"].append([len(x[1]["operations"]), {"unit": "setconf", 
                "order": ["updates", "current_update"], "data": x[1]["id"]}])
            messages = {
                "start": "Installing update %s of %s..." % (x[0], amount),
                "error": "Installation of update %s failed. See logs for details." % x[1]["id"],
                "success": "Update %s installed successfully. Please restart your system." % x[1]["id"]
                }
            self.app.ops.add_task(tasks=x[1]["operations"], messages=messages)
        self.app.ops.add_task(tasks=[[0, "unit": "updates", "order": "check_updates"]])
