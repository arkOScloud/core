"""
Functions to manage arkOS push updates.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

import json
import gnupg

from arkos import storage, signals, config, logger
from arkos.utilities import api, download, shell, DefaultMessage


def check_updates():
    """Check for updates from arkOS repo server."""
    updates = []
    gpg = gnupg.GPG()
    server = config.get("general", "repo_server")
    current = config.get("updates", "current_update", 0)
    # Fetch updates from registry server
    api_url = "https://{0}/api/v1/updates/{1}"
    data = api(api_url.format(server, str(current)), crit=True)
    for x in data["updates"]:
        ustr, u = str(x["tasks"]), json.loads(x["tasks"])
        # Get the update signature and test it
        sig_url = "https://{0}/api/v1/signatures/{1}"
        sig = api(sig_url.format(server, x["id"]), returns="raw", crit=True)
        with open("/tmp/{0}.sig".format(x["id"]), "w") as f:
            f.write(sig)
        v = gpg.verify_data("/tmp/{0}.sig".format(x["id"]), ustr)
        if v.trust_level is None:
            err_str = "Update {0} signature verification failed"
            logger.error(err_str.format(x["id"]))
            break
        else:
            data = {"id": x["id"], "name": x["name"], "date": x["date"],
                    "info": x["info"], "tasks": u}
            updates.append(data)
    storage.updates.set("updates", updates)
    return updates


def install_updates(message=DefaultMessage()):
    """
    Install all available updates from arkOS repo server.

    :param message message: Message object to update with status
    """
    updates = storage.updates.get("updates")
    if not updates:
        return
    signals.emit("updates", "pre_install")
    amount = len(updates)
    responses, ids = [], []
    for z in enumerate(updates):
        message.update("info", "{0} of {1}...".format(z[0] + 1, amount),
                       head="Installing updates")
        for x in sorted(z[1]["tasks"], key=lambda y: y["step"]):
            if x["unit"] == "shell":
                s = shell(x["order"], stdin=x.get("data", None))
                if s["code"] != 0:
                    responses.append((x["step"], s["stderr"]))
                    break
            elif x["unit"] == "fetch":
                try:
                    download(x["order"], x["data"], True)
                except Exception as e:
                    code = 1
                    if hasattr(e, "code"):
                        code = e.code
                    responses.append((x["step"], str(code)))
                    break
        else:
            ids.append(z[1]["id"])
            config.set("updates", "current_update", z[1]["id"])
            config.save()
            continue
        message.complete("error", "Installation of update {0} failed. "
                                  "See logs for details.".format(z[1]["id"]))
        logger.error(responses)
        break
    else:
        signals.emit("updates", "post_install")
        message.complete("success", "Please restart your system for the "
                         "updates to take effect.",
                         head="Updates installed successfully")
        return ids
