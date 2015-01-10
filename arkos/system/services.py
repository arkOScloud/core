import glob
import os

from arkos.utilities import shell
from arkos.connections import systemd, supervisor


class Service(object):
    def __init__(self, name="", stype="", state=False, enabled=False):
        self.name = name
        self.stype = stype
        self.state = state
        self.enabled = enabled

    def start(self):
        if self.stype == 'supervisor':
            supervisor.startProcess(self.name)
        else:
            systemd.StartUnit(self.name+".service", "replace")
    
    def stop(self):
        if self.stype == 'supervisor':
            supervisor.stopProcess(self.name)
        else:
            systemd.StopUnit(self.name+".service", "replace")
    
    def restart(self):
        if self.stype == 'supervisor':
            supervisor.stopProcess(self.name, wait=True)
            supervisor.startProcess(self.name)
        else:
            systemd.ReloadOrRestartUnit(self.name+".service", "replace")

    def real_restart(self):
        if self.stype == 'supervisor':
            self.restart()
        else:
            systemd.RestartUnit(self.name+".service", "replace")
    
    def get_log(self):
        if self.stype == 'supervisor':
            s = supervisor.tailProcessStdoutLog(self.name)
        else:
            s = shell("systemctl --no-ask-password status {}.service".format(self.name))["stdout"]
        return s

    def enable(self):
        if self.stype == 'supervisor':
            svd = get("supervisord")
            if os.path.exists(os.path.join('/etc/supervisor.d', self.name+'.ini.disabled')):
                os.rename(os.path.join('/etc/supervisor.d', self.name+'.ini.disabled'),
                    os.path.join('/etc/supervisor.d', self.name+'.ini'))
            if not svd.state == "running":
                svd.start()
            supervisor.addProcessGroup(self.name)
            self.start()
        else:
            systemd.EnableUnitFiles([self.name+".service"], False, True)

    def disable(self):
        if self.stype == 'supervisor':
            self.stop()
            supervisor.removeProcessGroup(self.name)
            os.rename(os.path.join('/etc/supervisor.d', self.name+'.ini'),
                os.path.join('/etc/supervisor.d', self.name+'.ini.disabled'))
        else:
            systemd.DisableUnitFiles([self.name+".service"], False)

    def delete(self):
        if self.stype == 'supervisor':
            self.stop()
            supervisor.removeProcessGroup(self.name)
            try:
                os.unlink(os.path.join('/etc/supervisor.d', self.name+'.ini'))
                os.unlink(os.path.join('/etc/supervisor.d', self.name+'.ini.disabled'))
            except:
                pass


def get(self, name=None):
    svcs = []

    for unit in systemd.ListUnits():
        if not unit[0].endswith(".service"):
            continue
        s = Service(name=unit[0].split(".service")[0], stype="system",
            state="running" if unit[3]=="active" else "stopped",
            enabled=systemd.GetUnitFileState(s.name+".service")==0)
        if name == s.name:
            return s
        svcs.append(s)

    if not os.path.exists('/etc/supervisor.d'):
        os.mkdir('/etc/supervisor.d')
    for x in os.listdir('/etc/supervisor.d'):
        s = Service(name=x.split(".ini")[0], stype="supervisor",
            state=supervisor.getProcessInfo(s.name)["statename"].lower(),
            enabled=not x.endswith("disabled"))
        if name == s.name:
            return s
        svcs.append(s)
    return sorted(svcs, key=lambda s: s.name) if not name else None
