import json
import gnupg

from arkos import storage, config, logger
from arkos.utilities import api, DefaultMessage


def check_updates():
    updates = []
    gpg = gnupg.GPG()
    server = config.get("general", "repo_server")
    current = config.get("updates", "current_update", 0)
    data = api("https://%s/updates/%s" % (server, current), crit=True)
    for x in data:
        ustr, u = x, json.loads(x)
        sig = api("https://%s/signatures/%s" % (server, u["id"]), 
            returns="raw", crit=True)
        with open("/tmp/%s.sig" % u["id"], "w") as f:
            f.write(sig)
        v = gpg.verify("/tmp/%s.sig" % u["id"], ustr)
        if not v.trust_level or not v.trust_level >= v.TRUST_FULLY:
            logger.error("Update %s signature verification failed" % u["id"])
            break
        else:
            updates.append(u)
    storage.updates.set("updates", updates)
    return updates

def install_updates(message=DefaultMessage()):
    updates = storage.updates.get("updates")
    if not updates:
        return
    amount = len(updates)
    responses = []
    for z in enumerate(updates):
        for x in sorted(x[1]["tasks"]):
            getout = False
            if message:
                message.update("info", "Installing update %s of %s..." % (z[0]+1, amount))
            getout = False
            if x[1]["unit"] == "shell":
                s = shell(x[1]["order"], stdin=x[1].get("data"))
                if s["code"] != 0:
                    responses.append((x[0], s["stderr"]))
                    getout = True
                    break
            elif x[1]["unit"] == "fetch":
                try:
                    download(x[1]["order"], x[1]["data"], True)
                except Exception, e:
                    code = 1
                    if hasattr(e, "code"):
                        code = e.code
                    responses.append((x[0], str(code)))
                    getout = True
                    break
        if getout and message:
            message.complete("error", "Installation of update %s failed. See logs for details." % z[1]["id"])
            break
        if not getout:
            config.set("updates", "current_update", z[1]["id"])
    else:
        if message:
            message.complete("success", "Installation of updates successful. Please restart your system.")
