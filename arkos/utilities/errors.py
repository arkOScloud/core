import traceback

from arkos import version
from utils import api


class MalformedObject(Exception):
    def __init__(self, raw):
        Exception.__init__(self)
        self.raw = raw
    
    def __str__(self):
        return "Malformed object encountered in storage: %s" % str(self.raw)


def process_exception(app, unit):
    app.logger.exception("Error in %s" % unit)
    x = traceback.format_exc()
    print x
    if app.conf.get("general", "send_errors", False):
        post = {"summary": "".join(x.splitlines()[-3:]), "trace": x, 
            "version": version(), "arch": app.conf.get("enviro", "arch", "Unknown")}
        try:
            api("https://%s/error" % app.conf.get("general", "repo_server"),
                post=post, crit=True)
        except Exception, e:
            app.logger.error("Error report submit failed - %s" % str(e))
