import ConfigParser
import glob
import os
import xmlrpclib

from dbus import SystemBus, Interface

from arkos.core.utilities import shell


class Services(object):
    def __init__(self):
        self._systemd_connect()
        self._supervisor_connect()
    
    def _systemd_connect(self):
        bus = SystemBus()
        systemd = bus.get_object("org.freedesktop.systemd1",
            "/org/freedesktop/systemd1")
        self.systemd = Interface(systemd, 
            dbus_interface="org.freedesktop.systemd1.Manager")

    def _supervisor_connect(self):
        s = xmlrpclib.Server("http://localhost:9001/RPC2")
        self.supervisor = s.supervisor

    def list_all(self):
        services, svcs = [], []

        for unit in self.systemd.ListUnits():
            if not unit[0].endswith(".service"):
                continue
            service = unit[0].split(".service")[0]
            services[service]["name"] = service
            services[service]["running"] = unit[3]=="active"
            services[service]["type"] = "system"
        for x in glob.iglob('/etc/systemd/system/*.wants/*.service'):
            service = x.split("/")[5]
            service = x.split(".service")[0]
            services[service]["enabled"] = True
        for x in services:
            svcs.append(services[x])

        if not os.path.exists('/etc/supervisor.d'):
            os.mkdir('/etc/supervisor.d')
        for x in os.listdir('/etc/supervisor.d'):
            x = x.split('.ini')[0]
            svcs.append({"name": x, "type": "supervisor",
                "status": self.get_status(x["name"], x["type"]),
                "enabled": self.get_enabled(x["name"], x["type"])})

        return sorted(svcs, key=lambda s: s["name"])

    def get_status(self, name, stype='system'):
        status = "unknown"
        if stype == 'supervisor':
            status = self.supervisor.getProcessInfo(name)["statename"].lower()
        else:
            for x in self.systemd.ListUnits():
                if name+".service" in x[0]:
                    status = x[3]
                    break
        return status

    def get_enabled(self, name, stype='system'):
        if stype == 'supervisor':
            return 'enabled' if os.path.exists(os.path.join('/etc/supervisor.d', name+'.ini')) else 'disabled'
        else:
            self.systemd.GetUnitFileState(name+".service")
            return 'disabled' if status != 0 else 'enabled'

    def get_log(self, name, stype='system'):
        if stype == 'supervisor':
            s = self.supervisor.tailProcessStdoutLog(name)
        else
            s = shell("systemctl --no-ask-password status {}.service".format(name))["stdout"]
        return s

    def start(self, name, stype='system'):
        if stype == 'supervisor':
            self.supervisor.startProcess(name)
        else:
            self.systemd.StartUnit(name+".service", "replace")

    def stop(self, name, stype='system'):
        if stype == 'supervisor':
            self.supervisor.stopProcess(name)
        else:
            self.systemd.StopUnit(name+".service", "replace")

    def restart(self, name, stype='system'):
        if stype == 'supervisor':
            self.supervisor.stopProcess(name, wait=True)
            self.supervisor.startProcess(name)
        else:
            self.systemd.ReloadOrRestartUnit(name+".service", "replace")

    def real_restart(self, name, stype='system'):
        if stype == 'supervisor':
            self.restart(name, "supervisor")
        else:
            self.systemd.RestartUnit(name+".service", "replace")

    def enable(self, name, stype='system'):
        if stype == 'supervisor':
            if os.path.exists(os.path.join('/etc/supervisor.d', name+'.ini.disabled')):
                os.rename(os.path.join('/etc/supervisor.d', name+'.ini.disabled'),
                    os.path.join('/etc/supervisor.d', name+'.ini'))
            if not self.get_status("supervisord") == "running":
                self.start("supervisord")
            self.supervisor.addProcessGroup(name)
            self.start(name, "supervisor")
        else:
            self.systemd.EnableUnitFiles([name+".service"], False, True)

    def disable(self, name, stype='system'):
        if stype == 'supervisor':
            self.stop(name, "supervisor")
            self.supervisor.removeProcessGroup(name)
            os.rename(os.path.join('/etc/supervisor.d', name+'.ini'),
                os.path.join('/etc/supervisor.d', name+'.ini.disabled'))
        else:
            self.systemd.DisableUnitFiles([name+".service"], False)

    def edit(self, name, opts, start=True, stype='supervisor'):
        if stype == 'supervisor':
            title = '%s:%s' % (opts['stype'], name)
            c = ConfigParser.RawConfigParser()
            c.add_section(title)
            for x in opts:
                if x != 'stype':
                    c.set(title, x, opts[x])
            with open(os.path.join('/etc/supervisor.d', name+'.ini'), 'w') as f:
                c.write(f)

    def delete(self, name, stype='supervisor'):
        if stype == 'supervisor':
            self.stop(name, "supervisor")
            self.supervisor.removeProcessGroup(name)
            try:
                os.unlink(os.path.join('/etc/supervisor.d', name+'.ini'))
                os.unlink(os.path.join('/etc/supervisor.d', name+'.ini.disabled'))
            except:
                pass
