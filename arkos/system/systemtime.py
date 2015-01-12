import ctypes, ctypes.util
import ntplib
import time

from arkos import config

ntp = ntplib.NTPClient()


class timespec(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


def verify_time(update=True):
    try:
        os = get_offset()
    except Exception, e:
        raise Exception('System time could not be retrieved. Error: %s' % str(e))
    if (os < -3600 or os > 3600) and update:
        set_datetime()
    return os

def get_datetime(display=''):
    return time.strftime(display) if display else time.localtime()

def get_idatetime():
    resp = ntp.request(config.get("general", "ntp_server"), version=3)
    return resp.tx_time

def set_datetime(dt=0):
    dt = int(dt) if dt else int(get_idatetime())
    librt = ctypes.CDLL(ctypes.util.find_library("rt"))
    ts = timespec()
    ts.tv_sec, ts.tv_nsec = dt, dt * 1000000
    librt.clock_settime(0, ctypes.byref(ts))

def convert(intime, infmt, outfmt):
    return time.strftime(outfmt, time.strptime(intime, infmt))

def get_serial_time():
    return time.strftime('%Y%m%d%H%M%S')

def get_date():
    return time.strftime(config.get("general", "date_format", "%d %b %Y"))

def get_time():
    return time.strftime(config.get("general", "time_format", "%H:%M"))

def get_offset():
    resp = ntp.request(config.get("general", "ntp_server"), version=3)
    return resp.offset
