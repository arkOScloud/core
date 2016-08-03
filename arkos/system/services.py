"""
Classes and functions for interacting with system management daemons.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE
"""

import configparser
from dbus.exceptions import DBusException
import os
import time

from arkos import conns, signals
from arkos.utilities import shell


class ActionError(Exception):
    """An exception raised when a start/stop action can't be performed."""
    
    def __init__(self, etype, emsg):
        """Initialize the exception."""
        self.etype = etype
        self.emsg = emsg


class Service:
    """
    A class representing a system-level service.

    Services can be of type ``systemd`` or ``supervisor``.
    """
    def __init__(self, name="", stype="", state=False, enabled=False, cfg={}):
        """
        Initialize the service.

        :param str name: Service name
        :param str stype: either ``systemd`` or ``supervisor``
        :param bool state: Running state of the service
        :param bool enabled: Service starts on boot?
        :param dict cfg: Config (for supervisor services)
        """
        self.name = name
        self.stype = stype
        self.state = state
        self.enabled = enabled
        self.cfg = cfg
        
    @property
    def sfname(self):
        """Return service file name."""
        if self.stype == "supervisor":
            return "{0}.ini".format(self.name)
        else:
            return "{0}.service".format(self.name)

    def add(self, enable=True):
        """Add a new Supervisor service."""
        signals.emit("services", "pre_add", self)
        title = "program:%s" % self.name
        c = ConfigParser.RawConfigParser()
        c.add_section(title)
        for x in self.cfg:
            c.set(title, x, self.cfg[x])
        with open(os.path.join("/etc/supervisor.d", self.name+".ini"), "w") as f:
            c.write(f)
        if enable:
            self.enable()
        signals.emit("services", "post_add", self)

    def start(self):
        """Start service."""
        signals.emit("services", "pre_start", self)
        if self.stype == "supervisor":
            supervisor_ping()
            try:
                conns.Supervisor.startProcess(self.name)
                signals.emit("services", "post_start", self)
            except:
                raise ActionError()
        else:
            # Send the start command to systemd
            try:
                path = conns.SystemD.LoadUnit(self.name+".service")
                conns.SystemD.StartUnit(self.name+".service", "replace")
            except DBusException as e:
                raise ActionError("dbus", str(e))
            timeout = 0
            time.sleep(1)
            # Wait for the service to start, raise exception if it fails
            while timeout < 10:
                data = conns.SystemDConnect(path, "org.freedesktop.DBus.Properties")
                data = data.GetAll("org.freedesktop.systemd1.Unit")
                if str(data["ActiveState"]) == "failed":
                    raise ActionError("svc", "The service failed to start. Please check `sudo systemctl -l status {}.service`".format(self.name))
                elif str(data["ActiveState"]) == "active":
                    self.state = "running"
                    signals.emit("services", "post_start", self)
                    break
                timeout += 1
                time.sleep(1)
            else:
                raise ActionError("svc", "The service start timed out. Please check `sudo systemctl -l status {}.service`".format(self.name))

    def stop(self):
        """Stop service."""
        signals.emit("services", "pre_stop", self)
        if self.stype == "supervisor":
            supervisor_ping()
            conns.Supervisor.stopProcess(self.name)
            signals.emit("services", "post_stop", self)
            self.state = "stopped"
        else:
            # Send the stop command to systemd
            try:
                path = conns.SystemD.LoadUnit(self.name+".service")
                conns.SystemD.StopUnit(self.name+".service", "replace")
            except DBusException as e:
                raise ActionError("dbus", str(e))
            timeout = 0
            time.sleep(1)
            # Wait for the service to stop, raise exception if it fails
            while timeout < 10:
                data = conns.SystemDConnect(path, "org.freedesktop.DBus.Properties")
                data = data.GetAll("org.freedesktop.systemd1.Unit")
                if str(data["ActiveState"]) in ["inactive", "failed"]:
                    self.state = "stopped"
                    signals.emit("services", "post_stop", self)
                    break
                timeout + 1
                time.sleep(1)
            else:
                raise ActionError("svc", "The service stop timed out. Please check `sudo systemctl -l status {}.service`".format(self.name))

    def restart(self, real=False):
        """Restart service."""
        signals.emit("services", "pre_restart", self)
        if self.stype == "supervisor":
            supervisor_ping()
            conns.Supervisor.stopProcess(self.name, wait=True)
            conns.Supervisor.startProcess(self.name)
            signals.emit("services", "post_restart", self)
        else:
            # Send the restart command to systemd
            try:
                path = conns.SystemD.LoadUnit(self.name+".service")
                if real:
                    conns.SystemD.RestartUnit(self.name+".service", "replace")
                else:
                    conns.SystemD.ReloadOrRestartUnit(self.name+".service", "replace")
            except DBusException as e:
                raise ActionError("dbus", str(e))
            timeout = 0
            time.sleep(1)
            # Wait for the service to restart, raise exception if it fails
            while timeout < 10:
                data = conns.SystemDConnect(path, "org.freedesktop.DBus.Properties")
                data = data.GetAll("org.freedesktop.systemd1.Unit")
                if str(data["ActiveState"]) == "failed":
                    raise ActionError("svc", "The service failed to restart. Please check `sudo systemctl -l status {}.service`".format(self.name))
                elif str(data["ActiveState"]) == "active":
                    self.state = "running"
                    signals.emit("services", "post_restart", self)
                    break
                timeout + 1
                time.sleep(1)
            else:
                raise ActionError("svc", "The service restart timed out. Please check `sudo systemctl -l status {}.service`".format(self.name))

    def get_log(self):
        """Get supervisor service logs."""
        if self.stype == "supervisor":
            supervisor_ping()
            s = conns.Supervisor.tailProcessStdoutLog(self.name)
        else:
            s = shell("systemctl --no-ask-password status {}.service".format(self.name))["stdout"]
        return s

    def enable(self):
        """Enable service to start on boot."""
        if self.stype == "supervisor":
            supervisor_ping()
            if os.path.exists(os.path.join("/etc/supervisor.d", self.name+".ini.disabled")):
                os.rename(os.path.join("/etc/supervisor.d", self.name+".ini.disabled"),
                    os.path.join("/etc/supervisor.d", self.name+".ini"))
            conns.Supervisor.restart()
        else:
            try:
                conns.SystemD.EnableUnitFiles([self.name+".service"], False, True)
            except DBusException as e:
                raise ActionError("dbus", str(e))
        self.enabled = True

    def disable(self):
        """Disable service starting on boot."""
        if self.stype == "supervisor":
            if self.state == "running":
                self.stop()
            os.rename(os.path.join("/etc/supervisor.d", self.name+".ini"),
                os.path.join("/etc/supervisor.d", self.name+".ini.disabled"))
            self.state = "stopped"
        else:
            try:
                conns.SystemD.DisableUnitFiles([self.name+".service"], False)
            except DBusException as e:
                raise ActionError("dbus", str(e))
        self.enabled = False

    def remove(self):
        """Remove supervisor service."""
        signals.emit("services", "pre_remove", self)
        if self.stype == "supervisor":
            supervisor_ping()
            if self.state == "running":
                self.stop()
            try:
                os.unlink(os.path.join("/etc/supervisor.d", self.name+".ini"))
                os.unlink(os.path.join("/etc/supervisor.d", self.name+".ini.disabled"))
            except:
                pass
            self.state = "stopped"
            self.enabled = False
            conns.Supervisor.restart()
            signals.emit("services", "post_remove", self)

    @property
    def as_dict(self):
        """Return service metadata as dict."""
        return {
            "id": self.name,
            "type": self.stype,
            "state": self.state,
            "running": self.state=="running",
            "enabled": self.enabled,
            "cfg": self.cfg,
            "is_ready": True
        }

    @property
    def serialized(self):
        """Return serializable service metadata as dict."""
        return self.as_dict


def get(id=None):
    """
    Get all service objects. If ID is specified, returns just one service.

    :param str id: Service ID to fetch
    :returns: Service(s)
    :rtype: Service or list thereof
    """
    svcs, files = [], {}

    # Get all unit files, loaded or not
    try:
        units = conns.SystemD.ListUnitFiles()
    except DBusException as e:
        raise ActionError("dbus", str(e))

    for unit in units:
        if not unit[0].endswith(".service"):
            continue
        sname = os.path.splitext(os.path.split(unit[0])[-1])[0]
        files[sname] = Service(name=sname, stype="system", state="stopped", enabled=unit[1]=="enabled")

    # Get all loaded services
    try:
        units = conns.SystemD.ListUnits()
    except DBusException as e:
        raise ActionError("dbus", str(e))

    for unit in units:
        if not unit[0].endswith(".service"):
            continue
        sname = unit[0].split(".service")[0]
        if not sname in files:
            files[sname] = Service(name=sname, stype="system", state="", enabled=unit[1]=="enabled")
        if "@" in sname and files.get(sname.split("@")[0] + "@", None):
            files[sname].enabled = files.get(sname.split("@")[0] + "@", None).enabled
        files[sname].state = "running" if unit[3]=="active" else "stopped"

    # If user requests a service with identifier and it's not running or enabled...
    if id and "@" in id and not id in files and (id.split("@")[0] + "@") in files:
        files[id] = Service(name=sname, stype="system", state="stopped",
            enabled=False)
        return files[id]

    # Match up loaded services with their unit files and show state
    for unit in files:
        if id == unit:
            return files[unit]
        if unit.endswith("@"):
            continue
        svcs.append(files[unit])

    # Get process info from Supervisor
    supervisor_ping()
    if not os.path.exists("/etc/supervisor.d"):
        os.mkdir("/etc/supervisor.d")
    for x in os.listdir("/etc/supervisor.d"):
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
    """Check to make sure Supervisor API connection is functional."""
    try:
        conns.Supervisor.getState()
    except:
        s = get("supervisord")
        s.restart()
