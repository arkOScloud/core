import ConfigParser
import glob
import os
import time

from arkos import conns
from arkos.utilities import shell


class ActionError(Exception):
    pass


class Service:
    def __init__(self, name="", stype="", state=False, enabled=False, cfg={}):
        self.name = name
        self.stype = stype
        self.state = state
        self.enabled = enabled
        self.cfg = cfg
    
    def add(self, enable=True):
        title = 'program:%s' % self.name
        c = ConfigParser.RawConfigParser()
        c.add_section(title)
        for x in self.cfg:
            c.set(title, x, self.cfg[x])
        with open(os.path.join('/etc/supervisor.d', self.name+'.ini'), 'w') as f:
            c.write(f)
        if enable:
            self.enable()

    def start(self):
        if self.stype == 'supervisor':
            supervisor_ping()
            try:
                conns.Supervisor.startProcess(self.name)
            except:
                raise ActionError()
        else:
            path = conns.SystemD.LoadUnit(self.name+".service")
            conns.SystemD.StartUnit(self.name+".service", "replace")
            timeout = 0
            time.sleep(1)
            while timeout < 10:
                data = conns.SystemDConnect(path, "org.freedesktop.DBus.Properties")
                data = data.GetAll('org.freedesktop.systemd1.Unit')
                if str(data["ActiveState"]) == "failed":
                    raise ActionError()
                elif str(data["ActiveState"]) == "active":
                    self.state = "running"
                    break
                timeout + 1
                time.sleep(1)
            else:
                raise ActionError()
    
    def stop(self):
        if self.stype == 'supervisor':
            supervisor_ping()
            conns.Supervisor.stopProcess(self.name)
            self.state = "stopped"
        else:
            path = conns.SystemD.LoadUnit(self.name+".service")
            conns.SystemD.StopUnit(self.name+".service", "replace")
            timeout = 0
            time.sleep(1)
            while timeout < 10:
                data = conns.SystemDConnect(path, "org.freedesktop.DBus.Properties")
                data = data.GetAll('org.freedesktop.systemd1.Unit')
                if str(data["ActiveState"]) in ["inactive", "failed"]:
                    self.state = "stopped"
                    break
                timeout + 1
                time.sleep(1)
            else:
                raise ActionError()
    
    def restart(self, real=False):
        if self.stype == 'supervisor':
            supervisor_ping()
            conns.Supervisor.stopProcess(self.name, wait=True)
            conns.Supervisor.startProcess(self.name)
        else:
            path = conns.SystemD.LoadUnit(self.name+".service")
            if real:
                conns.SystemD.RestartUnit(self.name+".service", "replace")
            else:
                conns.SystemD.ReloadOrRestartUnit(self.name+".service", "replace")
            timeout = 0
            time.sleep(1)
            while timeout < 10:
                data = conns.SystemDConnect(path, "org.freedesktop.DBus.Properties")
                data = data.GetAll('org.freedesktop.systemd1.Unit')
                if str(data["ActiveState"]) == "failed":
                    raise ActionError()
                elif str(data["ActiveState"]) == "active":
                    self.state = "running"
                    break
                timeout + 1
                time.sleep(1)
            else:
                raise ActionError()
    
    def get_log(self):
        if self.stype == 'supervisor':
            supervisor_ping()
            s = conns.Supervisor.tailProcessStdoutLog(self.name)
        else:
            s = shell("systemctl --no-ask-password status {}.service".format(self.name))["stdout"]
        return s

    def enable(self):
        if self.stype == 'supervisor':
            supervisor_ping()
            if os.path.exists(os.path.join('/etc/supervisor.d', self.name+'.ini.disabled')):
                os.rename(os.path.join('/etc/supervisor.d', self.name+'.ini.disabled'),
                    os.path.join('/etc/supervisor.d', self.name+'.ini'))
            conns.Supervisor.restart()
        else:
            conns.SystemD.EnableUnitFiles([self.name+".service"], False, True)
        self.enabled = True

    def disable(self):
        if self.stype == 'supervisor':
            if self.state == "running":
                self.stop()
            os.rename(os.path.join('/etc/supervisor.d', self.name+'.ini'),
                os.path.join('/etc/supervisor.d', self.name+'.ini.disabled'))
            self.state = "stopped"
        else:
            conns.SystemD.DisableUnitFiles([self.name+".service"], False)
        self.enabled = False

    def remove(self):
        if self.stype == 'supervisor':
            supervisor_ping()
            if self.state == "running":
                self.stop()
            try:
                os.unlink(os.path.join('/etc/supervisor.d', self.name+'.ini'))
                os.unlink(os.path.join('/etc/supervisor.d', self.name+'.ini.disabled'))
            except:
                pass
            self.state = "stopped"
            self.enabled = False
            conns.Supervisor.restart()
    
    def as_dict(self):
        return {
            "id": self.name,
            "type": self.stype,
            "state": self.state,
            "running": self.state=="running",
            "enabled": self.enabled,
            "cfg": self.cfg,
            "is_ready": True
        }


def get(id=None):
    svcs, files = [], {}
    
    for unit in conns.SystemD.ListUnitFiles():
        if not unit[0].endswith(".service"):
            continue
        sname = os.path.splitext(os.path.split(unit[0])[-1])[0]
        files[sname] = Service(name=sname, stype="system", state="stopped", enabled=unit[1]=="enabled")

    for unit in conns.SystemD.ListUnits():
        if not unit[0].endswith(".service"):
            continue
        sname = unit[0].split(".service")[0]
        if not sname in files:
            continue
        files[sname].state = "running" if unit[3]=="active" else "stopped"
    
    for unit in files:
        if id == unit:
            return files[unit]
        svcs.append(files[unit])

    supervisor_ping()
    if not os.path.exists('/etc/supervisor.d'):
        os.mkdir('/etc/supervisor.d')
    for x in os.listdir('/etc/supervisor.d'):
        c = ConfigParser.RawConfigParser()
        c.read(os.path.join("/etc/supervisor.d", x))
        cfg = {}
        for y in c.items(c.sections()[0]):
            cfg[y[0]] = y[1]
        name = x.split(".ini")[0]
        try:
            conns.Supervisor.getProcessInfo(name)
        except:
            continue
        s = Service(name=name, stype="supervisor",
            state=conns.Supervisor.getProcessInfo(name)["statename"].lower() if not x.endswith("disabled") else "stopped",
            enabled=not x.endswith("disabled"), cfg=cfg)
        if id == s.name:
            return s
        svcs.append(s)
    return sorted(svcs, key=lambda s: s.name) if not id else None

def supervisor_ping():
    try:
        conns.Supervisor.getState()
    except:
        s = get("supervisord")
        s.restart()
