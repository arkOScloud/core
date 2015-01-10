import glob
import os

from arkos import conns
from arkos.utilities import shell


class Service(object):
    def __init__(self, name="", stype="", state=False, enabled=False):
        self.name = name
        self.stype = stype
        self.state = state
        self.enabled = enabled

    def start(self):
        if self.stype == 'supervisor':
            conns.Supervisor.startProcess(self.name)
        else:
            conns.SystemD.StartUnit(self.name+".service", "replace")
    
    def stop(self):
        if self.stype == 'supervisor':
            conns.Supervisor.stopProcess(self.name)
        else:
            conns.SystemD.StopUnit(self.name+".service", "replace")
        self.state = "stopped"
    
    def restart(self):
        if self.stype == 'supervisor':
            conns.Supervisor.stopProcess(self.name, wait=True)
            conns.Supervisor.startProcess(self.name)
        else:
            conns.SystemD.ReloadOrRestartUnit(self.name+".service", "replace")

    def real_restart(self):
        if self.stype == 'supervisor':
            self.restart()
        else:
            conns.SystemD.RestartUnit(self.name+".service", "replace")
    
    def get_log(self):
        if self.stype == 'supervisor':
            s = conns.Supervisor.tailProcessStdoutLog(self.name)
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
            conns.Supervisor.addProcessGroup(self.name)
            self.start()
            self.state = "running"
        else:
            conns.SystemD.EnableUnitFiles([self.name+".service"], False, True)
        self.enabled = True

    def disable(self):
        if self.stype == 'supervisor':
            self.stop()
            conns.Supervisor.removeProcessGroup(self.name)
            os.rename(os.path.join('/etc/supervisor.d', self.name+'.ini'),
                os.path.join('/etc/supervisor.d', self.name+'.ini.disabled'))
            self.state = "stopped"
        else:
            conns.SystemD.DisableUnitFiles([self.name+".service"], False)
        self.enabled = False

    def delete(self):
        if self.stype == 'supervisor':
            self.stop()
            conns.Supervisor.removeProcessGroup(self.name)
            try:
                os.unlink(os.path.join('/etc/supervisor.d', self.name+'.ini'))
                os.unlink(os.path.join('/etc/supervisor.d', self.name+'.ini.disabled'))
            except:
                pass
            self.state = "stopped"
            self.enabled = False


def get(name=None):
    svcs = []

    for unit in conns.SystemD.ListUnits():
        if not unit[0].endswith(".service"):
            continue
        try:
            enabled = conns.SystemD.GetUnitFileState(unit[0])=="enabled"
        except:
            enabled = False
        s = Service(name=unit[0].split(".service")[0], stype="system",
            state="running" if unit[3]=="active" else "stopped",
            enabled=enabled)
        if name == s.name:
            return s
        svcs.append(s)

    if not os.path.exists('/etc/supervisor.d'):
        os.mkdir('/etc/supervisor.d')
    for x in os.listdir('/etc/supervisor.d'):
        s = Service(name=x.split(".ini")[0], stype="supervisor",
            state=conns.Supervisor.getProcessInfo(s.name)["statename"].lower(),
            enabled=not x.endswith("disabled"))
        if name == s.name:
            return s
        svcs.append(s)
    return sorted(svcs, key=lambda s: s.name) if not name else None
