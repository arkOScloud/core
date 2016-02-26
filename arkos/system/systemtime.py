import ctypes, ctypes.util
import datetime
import ntplib
import os
import time

from arkos import config, signals

ntp = ntplib.NTPClient()


class timespec(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


def verify_time(update=True, crit=True):
    # Verifies system time with NTP, sets it if it is more than an hour off
    try:
        os = get_offset()
    except Exception, e:
        if crit:
            raise Exception("System time could not be retrieved. Error: %s" % str(e))
        else:
            return "UNKNOWN"
    if (os < -3600 or os > 3600) and update:
        set_datetime()
    return os

def get_offset():
    # Get the amount of seconds that system time is off from NTP
    resp = ntp.request(config.get("general", "ntp_server"), version=3)
    return resp.offset

def get_date():
    return time.strftime(config.get("general", "date_format", "%d %b %Y"))

def get_time():
    return time.strftime(config.get("general", "time_format", "%H:%M"))

def get_unix_time(ts=None, fmt="%Y-%m-%dT%H:%M:%S"):
    # Gets Unix time from provided timestamp (or current time if None)
    if ts:
        return int(datetime.datetime.strptime(ts, fmt).strftime("%s"))
    else:
        return int(time.time())

def get_datetime():
    return get_date() + " " + get_time()

def set_datetime(ut=0):
    # Sets system time from provided Unix timestamp (or current time via NTP)
    ut = int(ut) if ut else int(get_idatetime())
    librt = ctypes.CDLL(ctypes.util.find_library("rt"), use_errno=True)
    ts = timespec()
    ts.tv_sec, ts.tv_nsec = ut, 0
    res = librt.clock_settime(0, ctypes.byref(ts))
    if res == -1:
        raise Exception("Could not set time: %s" % os.strerror(ctypes.get_errno()))
    signals.emit("config", "time_changed", ut)

def get_idatetime():
    # Gets date and time from NTP server
    resp = ntp.request(config.get("general", "ntp_server"), version=3)
    return resp.tx_time

def get_serial_time():
    # Get current time in serial format (e.g. 20150420213000)
    return time.strftime("%Y%m%d%H%M%S")

def get_iso_time(ts=None, fmt="%Y%m%d%H%M%S"):
    # Gets time in ISO-8601 format from provided timestamp (or current time if None)
    tz = time.strftime("%z")
    tz = tz[:3]+":"+tz[3:]
    if ts and fmt == "unix":
        return datetime.datetime.fromtimestamp(ts).isoformat()+tz
    elif ts:
        return datetime.datetime.strptime(ts, fmt).isoformat()+tz
    else:
        return datetime.datetime.now().isoformat()+tz

def ts_to_datetime(ts, fmt="%Y%m%d%H%M%S"):
    if fmt == "unix":
        return datetime.datetime.fromtimestamp(ts)
    else:
        return datetime.datetime.strptime(ts, fmt)
