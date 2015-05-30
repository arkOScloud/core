#coding: utf-8
import os
import psutil
import time

from arkos import config


def get_all():
    return {
        "load": get_load(),
        "temp": get_temp(),
        "ram": get_ram(),
        "cpu": get_cpu(),
        "swap": get_swap(),
        #"space": get_space(),
        "uptime": get_uptime()
    }

def get_load():
    return os.getloadavg()

def get_temp():
    # TODO: replace this with libsensors.so / PySensors
    if config.get("enviro", "board").startswith("Raspberry Pi"):
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return "%3.1f°C"%(float(f.read().rstrip("\n"))/1000)
    else:
        if os.path.exists("/sys/class/hwmon/hwmon1/temp1_input"):
            with open("/sys/class/hwmon/hwmon1/temp1_input", "r") as f:
                return "%3.1f°C"%(float(f.read().rstrip("\n"))/1000)
    return ""

def get_ram():
    s = psutil.virtual_memory()
    a = int(s.used) - (int(s.cached) + int(s.buffers))
    return (a, int(s.total), int(s.percent))

def get_cpu():
    return psutil.cpu_percent(interval=1)

def get_swap():
    s = psutil.swap_memory()
    return (int(s.used), int(s.total))

def get_space():
    result = {}
    s = psutil.disk_partitions()
    for x in s:
        r = psutil.disk_usage(x.device)
        result[x.device] = [r.used, r.total, r.percent]
    return result

def get_uptime():
    minute = 60
    hour = minute * 60
    day = hour * 24

    d = h = m = 0

    s = int(time.time()) - int(psutil.boot_time())

    d = s / day
    s -= d * day
    h = s / hour
    s -= h * hour
    m = s / minute
    s -= m * minute

    uptime = ""
    if d > 1:
        uptime = "%d days, "%d
    elif d == 1:
        uptime = "1 day, "

    return uptime + "%d:%02d:%02d"%(h,m,s)
