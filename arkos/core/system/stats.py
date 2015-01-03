#coding: utf-8
import os
import psutil
import time


def get_all(self):
    return {
        "load": get_load(),
        "temp": get_temp(),
        "ram": get_ram(),
        "swap": get_swap(),
        "uptime": get_uptime()
    }

def get_load(self):
    return os.getloadavg()

def get_temp(self, hw=""):
    # TODO: replace this with libsensors.so / PySensors
    if hw == 'Raspberry Pi':
        return '%3.1f°C'%(float(shell('cat /sys/class/thermal/thermal_zone0/temp').split('\n')[0])/1000)
    else:
        if os.path.exists('/sys/class/hwmon/hwmon1/temp1_input'):
            return '%3.1f°C'%(float(shell('cat /sys/class/hwmon/hwmon1/temp1_input'))/1000)
    return ''

def get_ram(self):
    s = psutil.virtual_memory()
    a = int(s.used) - (int(s.cached) + int(s.buffers))
    return (a, int(s.total), int(s.percent))

def get_swap(self):
    s = psutil.swap_memory()
    return (int(s.used), int(s.total))

def get_uptime(self):
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
