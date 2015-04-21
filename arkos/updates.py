import json
import gnupg

from arkos import storage, signals, config, logger
from arkos.utilities import api, download, shell, DefaultMessage


def check_updates():
    updates = []
    gpg = gnupg.GPG()
    server = config.get("general", "repo_server")
    current = config.get("updates", "current_update", 0)
    # Fetch updates from registry server
    data = api("https://%s/api/v1/updates/%s" % (server, str(current)), crit=True)
    for x in data["updates"]:
        ustr, u = str(x["tasks"]), json.loads(x["tasks"])
        # Get the update signature and test it
        sig = api("https://%s/api/v1/signatures/%s" % (server, x["id"]), 
            returns="raw", crit=True)
        with open("/tmp/%s.sig" % x["id"], "w") as f:
            f.write(sig)
        v = gpg.verify_data("/tmp/%s.sig" % x["id"], ustr)
        if v.trust_level == None:
            logger.error("Update %s signature verification failed" % x["id"])
            break
        else:
            updates.append({"id": x["id"], "name": x["name"], "date": x["date"], 
                "info": x["info"], "tasks": u})
    storage.updates.set("updates", updates)
    return updates

def install_updates(message=DefaultMessage()):
    updates = storage.updates.get("updates")
    if not updates:
        return
    signals.emit("updates", "pre_install")
    amount = len(updates)
    responses, ids = [], []
    for z in enumerate(updates):
        message.update("info", "%s of %s..." % (z[0]+1, amount), head="Installing updates")
        for x in sorted(z[1]["tasks"], key=lambda y: y["step"]):
            getout = False
            if x["unit"] == "shell":
                s = shell(x["order"], stdin=x.get("data", None))
                if s["code"] != 0:
                    responses.append((x["step"], s["stderr"]))
                    getout = True
                    break
            elif x["unit"] == "fetch":
                try:
                    download(x["order"], x["data"], True)
                except Exception, e:
                    code = 1
                    if hasattr(e, "code"):
                        code = e.code
                    responses.append((x["step"], str(code)))
                    getout = True
                    break
        else:
            ids.append(z[1]["id"])
            config.set("updates", "current_update", z[1]["id"])
            config.save()
            continue
        message.complete("error", "Installation of update %s failed. See logs for details." % str(z[1]["id"]))
        print responses
        break
    else:
        signals.emit("updates", "post_install")
        message.complete("success", "Please restart your system for the updates to take effect.", head="Updates installed successfully")
        return ids
